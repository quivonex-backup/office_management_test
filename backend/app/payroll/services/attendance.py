"""
Day-by-day attendance classification for a payroll period.

Only imports from common.py — no cycles with computation/processing.

Design note:
  - Paid holiday    -> day off, paid (counted in `holiday_days`)
  - Weekly off      -> day off, paid (counted in `weekly_off_days`)
  - Unpaid holiday  -> WORKING DAY (falls through to presence logic)
  - WORKING_DAY     -> classified by AttendanceRecord.status
"""

from datetime import timedelta
from decimal import Decimal

from app.attendance.models import AttendanceRecord
from app.attendance.services import get_employee_shift
from app.calendar_app.services import get_calendar_day
from app.leave.models import LeaveApplication

from .common import ZERO, ONE


def build_leave_map(employee, period_start, period_end):
    """
    Return {date: is_paid_leave_bool} for approved leave days that overlap
    the period. If any overlapping approved leave is paid, paid wins.
    """
    leave_map = {}

    apps = LeaveApplication.objects.filter(
        employee=employee,
        status="APPROVED",
        start_date__lte=period_end,
        end_date__gte=period_start,
    ).select_related("leave_type")

    for app in apps.iterator():
        is_paid = bool(app.leave_type.is_paid)
        cursor = max(app.start_date, period_start)
        end = min(app.end_date, period_end)
        while cursor <= end:
            if leave_map.get(cursor) is not True:
                leave_map[cursor] = is_paid
            cursor += timedelta(days=1)

    return leave_map


def compute_attendance_counts(
    employee, organization, period_start, period_end, settings,
):
    """
    Walk the period day by day and classify each day.

    Per-day precedence:
        1. HOLIDAY (paid)       -> holiday_days
        2. HOLIDAY (unpaid)     -> treated as WORKING DAY (falls through)
        3. WEEKLY_OFF           -> weekly_off_days
        4. NO_SHIFT_ASSIGNED    -> skipped entirely
        5. WORKING_DAY          -> classified by AttendanceRecord.status

    Returns dict with:
      counts, overtime_minutes, warnings, requires_review, sources.
    """
    records = AttendanceRecord.objects.filter(
        organization=organization,
        employee=employee,
        work_date__range=(period_start, period_end),
    ).only("work_date", "status", "overtime_minutes")
    record_by_date = {r.work_date: r for r in records}

    leave_map = build_leave_map(employee, period_start, period_end)

    counts = {
        "working_days": ZERO,
        "present_days": ZERO,
        "half_days": ZERO,
        "absent_days": ZERO,
        "paid_leave_days": ZERO,
        "unpaid_leave_days": ZERO,
        "holiday_days": ZERO,
        "weekly_off_days": ZERO,
    }
    sources = {
        "paid_holiday_days": ZERO,
        "unpaid_holiday_as_working_days": ZERO,
        "unpaid_leave_absorbed_into_absent": ZERO,
        "missing_record_absent": ZERO,
    }

    overtime_minutes = 0
    warnings = []
    requires_review = False

    missing_action = settings.missing_attendance_action

    def _handle_missing_record(day):
        nonlocal requires_review
        if missing_action == "SKIP":
            warnings.append(
                f"No attendance record on {day}; skipped (no deduction)."
            )
            return
        if missing_action == "ABSENT":
            counts["absent_days"] += ONE
            sources["missing_record_absent"] += ONE
            warnings.append(
                f"No attendance record on {day}; treated as absent."
            )
            return
        requires_review = True
        warnings.append(
            f"No attendance record on {day}; held for review."
        )

    current = period_start
    while current <= period_end:
        shift = get_employee_shift(employee, organization, current)
        cal = get_calendar_day(
            organization=organization,
            target_date=current,
            shift=shift,
        )
        day_type = cal.get("day_type")

        # ---- Paid holiday: day off ----
        if day_type == "HOLIDAY" and cal.get("pay_type") != "UNPAID":
            counts["holiday_days"] += ONE
            sources["paid_holiday_days"] += ONE
            current += timedelta(days=1)
            continue

        # ---- Weekly off: day off ----
        if day_type == "WEEKLY_OFF":
            counts["weekly_off_days"] += ONE
            current += timedelta(days=1)
            continue

        # ---- No shift assigned for this employee on this date ----
        if day_type == "NO_SHIFT_ASSIGNED":
            current += timedelta(days=1)
            continue

        # ---- Everything else is a working day ----
        # (WORKING_DAY, or HOLIDAY with pay_type == "UNPAID")
        if day_type == "HOLIDAY" and cal.get("pay_type") == "UNPAID":
            sources["unpaid_holiday_as_working_days"] += ONE

        counts["working_days"] += ONE

        record = record_by_date.get(current)

        if record is None:
            _handle_missing_record(current)
            current += timedelta(days=1)
            continue

        status = record.status

        if status == "PRESENT":
            counts["present_days"] += ONE
            overtime_minutes += record.overtime_minutes or 0

        elif status == "HALF_DAY":
            counts["half_days"] += ONE
            overtime_minutes += record.overtime_minutes or 0

        elif status == "ABSENT":
            counts["absent_days"] += ONE

        elif status == "ON_LEAVE":
            is_paid = leave_map.get(current)
            if is_paid is None:
                counts["unpaid_leave_days"] += ONE
                sources["unpaid_leave_absorbed_into_absent"] += ONE
                warnings.append(
                    f"{current}: ON_LEAVE without matching approved leave; "
                    f"counted as unpaid leave."
                )
            elif is_paid:
                counts["paid_leave_days"] += ONE
            else:
                counts["unpaid_leave_days"] += ONE
                sources["unpaid_leave_absorbed_into_absent"] += ONE

        elif status in {"INCOMPLETE", "PENDING_REVIEW"}:
            requires_review = True
            warnings.append(
                f"{current}: attendance {status.lower()}; "
                f"held for review (no deduction)."
            )

        else:
            requires_review = True
            warnings.append(
                f"{current}: unrecognised attendance status "
                f"'{status}'; held for review."
            )

        current += timedelta(days=1)

    return {
        "counts": counts,
        "overtime_minutes": overtime_minutes,
        "warnings": warnings,
        "requires_review": requires_review,
        "sources": sources,
    }
