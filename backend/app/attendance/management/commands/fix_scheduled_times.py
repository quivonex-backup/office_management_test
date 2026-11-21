"""
One-time repair for attendance rows created while TIME_ZONE was 'UTC'.

Those rows have scheduled_start / scheduled_end stored 5h30m too late
(09:00 "UTC" instead of 09:00 IST), so late / early-departure / overtime /
HALF_DAY were calculated against the wrong shift times.

Place at:  app/attendance/management/commands/fix_scheduled_times.py
(create the `management/` and `commands/` folders with empty __init__.py files)

Usage:
    python manage.py fix_scheduled_times                       # dry run, prints changes
    python manage.py fix_scheduled_times --apply               # write changes
    python manage.py fix_scheduled_times --apply --from-date 2026-10-01 --to-date 2026-11-30

Rows that have an APPLIED correction (admin-approved) or no check-in (ABSENT,
ON_LEAVE) keep their status; only their scheduled times are repaired.
Everything else is recalculated with calculate_attendance(). Re-run "Generate again" on any payroll run afterwards.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from app.attendance.models import AttendanceCorrection, AttendanceRecord
from app.attendance.services import (
    calculate_attendance,
    get_attendance_settings,
    get_shift_datetimes,
)


class Command(BaseCommand):
    help = "Repair scheduled_start/end and recalculate attendance rows made under TIME_ZONE=UTC."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write the changes (default is a dry run).")
        parser.add_argument("--from-date", help="YYYY-MM-DD")
        parser.add_argument("--to-date", help="YYYY-MM-DD")

    def handle(self, *args, **opts):
        apply_changes = opts["apply"]

        qs = AttendanceRecord.objects.select_related("organization", "shift").order_by("work_date", "id")
        if opts.get("from_date"):
            qs = qs.filter(work_date__gte=opts["from_date"])
        if opts.get("to_date"):
            qs = qs.filter(work_date__lte=opts["to_date"])

        corrected_ids = set(
            AttendanceCorrection.objects.filter(status="APPLIED")
            .values_list("attendance_id", flat=True)
        )
        settings_cache = {}

        fixed = recalculated = status_changed = 0

        for rec in qs.iterator():
            org_id = rec.organization_id
            if org_id not in settings_cache:
                settings_cache[org_id] = get_attendance_settings(rec.organization)

            start, end = get_shift_datetimes(rec.shift, rec.work_date, settings_cache[org_id])

            if rec.scheduled_start == start and rec.scheduled_end == end:
                continue

            fixed += 1
            old_status = rec.status
            self.stdout.write(
                f"#{rec.id} {rec.employee_id} {rec.work_date}: "
                f"{rec.scheduled_start} -> {start} | {rec.scheduled_end} -> {end}"
            )

            if not apply_changes:
                continue

            with transaction.atomic():
                rec.scheduled_start = start
                rec.scheduled_end = end
                rec.save(update_fields=["scheduled_start", "scheduled_end", "updated_at"])

                if rec.id in corrected_ids:
                    self.stdout.write("    has an applied correction: status kept")
                    continue

                if not rec.check_in:
                    # ABSENT / ON_LEAVE / placeholder rows have no punches.
                    # calculate_attendance() would reset them to INCOMPLETE,
                    # so only the scheduled times are repaired.
                    self.stdout.write("    no check-in: status kept")
                    continue

                calculate_attendance(rec)
                recalculated += 1
                if rec.status != old_status:
                    status_changed += 1
                    self.stdout.write(f"    status {old_status} -> {rec.status}")

        mode = "APPLIED" if apply_changes else "DRY RUN (nothing written)"
        self.stdout.write(self.style.SUCCESS(
            f"{mode}: {fixed} rows need repair, {recalculated} recalculated, {status_changed} status changes."
        ))
