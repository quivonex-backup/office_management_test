from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from app.calendar_app.services import get_calendar_day
from app.employees.models import Employee

from .models import AttendanceRecord, AttendanceSettings
from .services import (
    get_employee_shift,
    get_shift_datetimes,
    mark_employee_absent,
)


# An employee may check out up to four hours after the scheduled end.
# For overnight shifts, scheduled_end is on the following calendar day.
STALE_CHECKOUT_GRACE_HOURS = 4

# Fallback only when an attendance record has no scheduled_end.
STALE_CHECKOUT_FALLBACK_HOURS = 18


# =========================================================
# AUTO MARK ABSENT
# Scheduled in config/settings.py CELERY_BEAT_SCHEDULE (every 5 minutes).
# Needs a running worker + beat:  celery -A config worker -l info
#                                 celery -A config beat -l info
# =========================================================

@shared_task(name="app.attendance.tasks.auto_mark_absent_task")
def auto_mark_absent_task():
    """
    Mark employees absent after their configured cutoff.

    Rules:
    - Only organizations with AttendanceSettings.auto_mark_absent = True.
    - Process the current local work date only.
    - Active employees with an active shift assignment; holidays and weekly
      offs are skipped.
    - Cutoff = shift start + absent_after_minutes.
    - Never overwrite a check-in or any status other than INCOMPLETE
      (approved leave is already ON_LEAVE).
    - A late check-in after the cutoff is still accepted by the punch API
      (it only refuses when a check-in exists).
    """
    now = timezone.now()
    work_date = timezone.localdate(now)

    organizations_checked = 0
    employees_checked = 0
    employees_marked_absent = 0
    employees_skipped = 0

    settings_list = (
        AttendanceSettings.objects
        .filter(auto_mark_absent=True, organization__is_active=True)
        .select_related("organization")
    )

    for attendance_settings in settings_list:
        organization = attendance_settings.organization
        organizations_checked += 1

        employees = Employee.objects.filter(
            organization=organization,
            is_active=True,
            employment_status="ACTIVE",
        ).iterator(chunk_size=500)

        for employee in employees:
            employees_checked += 1

            # Not employed yet on this date.
            if employee.joining_date and employee.joining_date > work_date:
                employees_skipped += 1
                continue

            shift = get_employee_shift(
                employee=employee,
                organization=organization,
                work_date=work_date,
            )
            if shift is None:
                employees_skipped += 1
                continue

            calendar_day = get_calendar_day(
                organization=organization,
                target_date=work_date,
                shift=shift,
            )
            if calendar_day["day_type"] != "WORKING_DAY":
                employees_skipped += 1
                continue

            scheduled_start, _ = get_shift_datetimes(
                shift=shift,
                work_date=work_date,
                attendance_settings=attendance_settings,
            )
            absence_cutoff = scheduled_start + timedelta(
                minutes=attendance_settings.absent_after_minutes
            )
            if now < absence_cutoff:
                continue

            existing = AttendanceRecord.objects.filter(
                organization=organization,
                employee=employee,
                work_date=work_date,
            ).first()
            if existing:
                if existing.check_in:
                    continue
                if existing.status != "INCOMPLETE":
                    employees_skipped += 1
                    continue

            attendance = mark_employee_absent(
                employee=employee,
                organization=organization,
                work_date=work_date,
            )
            if attendance.status == "ABSENT":
                employees_marked_absent += 1

    return {
        "status": "completed",
        "work_date": str(work_date),
        "organizations_checked": organizations_checked,
        "employees_checked": employees_checked,
        "employees_marked_absent": employees_marked_absent,
        "employees_skipped": employees_skipped,
    }


# =========================================================
# FLAG STALE ATTENDANCE
# =========================================================

@shared_task(name="app.attendance.tasks.flag_stale_attendance_task")
def flag_stale_attendance_task():
    """
    Move check-ins without a check-out to PENDING_REVIEW once the checkout
    window has passed (scheduled end + 4 h, or check-in + 18 h when there is
    no schedule). Never invents a checkout time; overtime is cleared.
    The same rule already runs on the employee's next punch; this task makes
    it visible to managers without waiting for that punch.
    """
    now = timezone.now()
    records_checked = 0
    records_flagged = 0

    open_ids = (
        AttendanceRecord.objects.filter(
            check_in__isnull=False,
            check_out__isnull=True,
            status="INCOMPLETE",
        )
        .order_by("pk")
        .values_list("pk", flat=True)
        .iterator(chunk_size=500)
    )

    for attendance_id in open_ids:
        records_checked += 1

        with transaction.atomic():
            attendance = (
                AttendanceRecord.objects.select_for_update()
                .filter(pk=attendance_id)
                .first()
            )
            if (
                attendance is None
                or attendance.check_in is None
                or attendance.check_out is not None
                or attendance.status != "INCOMPLETE"
            ):
                continue

            if attendance.scheduled_end is not None:
                deadline = attendance.scheduled_end + timedelta(hours=STALE_CHECKOUT_GRACE_HOURS)
            else:
                deadline = attendance.check_in + timedelta(hours=STALE_CHECKOUT_FALLBACK_HOURS)
            if now <= deadline:
                continue

            attendance.status = "PENDING_REVIEW"
            attendance.net_work_minutes = 0
            attendance.overtime_minutes = 0
            attendance.save(update_fields=["status", "net_work_minutes", "overtime_minutes", "updated_at"])
            records_flagged += 1

    return {
        "status": "completed",
        "checked_at": now.isoformat(),
        "records_checked": records_checked,
        "records_flagged_for_review": records_flagged,
    }
