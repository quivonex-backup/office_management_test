"""
Day-by-day attendance classification for a payroll period.

Only imports from common.py — no cycles with computation/processing.

Rules (per calendar day, first match wins):
  0. Outside employment (before joining_date / after resignation_date)
                        -> not_employed_days (unpaid)
  1. Paid holiday       -> day off, paid           (holiday_days)
  2. Weekly off         -> day off, paid           (weekly_off_days)
  3. No shift assigned  -> skipped, UNLESS the employee has an attendance
                           record that day (then it is a working day)
  4. Everything else    -> WORKING DAY, classified by AttendanceRecord.status
                           (an unpaid holiday is a working day too)

Notes:
  * Attendance on a weekly off / paid holiday earns nothing extra; it is only
    recorded in `sources["worked_on_off_days"]` for the audit trail.
  * Status is trusted as-is. Corrections approved by an admin are final;
    payroll never re-derives a status from punch times.
  * Today and later days with no finished record are NOT treated as absent.
  * An approved leave day with no attendance row is counted as leave.

The classification itself lives in `classify_period()`, which takes plain
callables/dicts so it can be unit-tested without a database.
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from app.attendance.models import AttendanceRecord, EmployeeShiftAssignment
from app.attendance.services import get_employee_shift
from app.calendar_app.services import get_calendar_day
from app.leave.models import LeaveApplication

from .common import ZERO, ONE


WORKED_STATUSES = {"PRESENT", "HALF_DAY"}
REVIEW_STATUSES = {"INCOMPLETE", "PENDING_REVIEW"}


# =========================================================
# LEAVE MAP
# =========================================================

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


# =========================================================
# PURE CLASSIFIER (no database access)
# =========================================================

def classify_period(
    period_start,
    period_end,
    *,
    day_info,
    records,
    leave_map,
    missing_action,
    joining_date=None,
    exit_date=None,
    today=None,
    fallback_day_info=None,
):
    """
    day_info(date)          -> calendar dict for the employee's shift
                               (keys: day_type, pay_type)
    records                 -> {date: obj with .status and .overtime_minutes}
    leave_map               -> {date: is_paid}
    missing_action          -> "SKIP" | "ABSENT" | "REVIEW"
    fallback_day_info(date) -> calendar dict used only for days outside the
                               employment window (to count how many of them
                               would have been working days)
    today                   -> days on/after this date are not evaluated
                               unless a finished record already exists
    """
    counts = {
        "working_days": ZERO,
        "present_days": ZERO,
        "half_days": ZERO,
        "absent_days": ZERO,
        "paid_leave_days": ZERO,
        "unpaid_leave_days": ZERO,
        "holiday_days": ZERO,
        "weekly_off_days": ZERO,
        "not_employed_days": ZERO,
        "not_employed_working_days": ZERO,
    }
    sources = {
        "paid_holiday_days": ZERO,
        "unpaid_holiday_as_working_days": ZERO,
        "unpaid_leave_absorbed_into_absent": ZERO,
        "missing_record_absent": ZERO,
        "missing_record_skipped": ZERO,
        "leave_without_record": ZERO,
        "no_shift_days_not_counted": ZERO,
        "no_shift_days_with_record": ZERO,
        "worked_on_off_days": ZERO,
        "held_for_review_days": ZERO,
        "not_evaluated_days": ZERO,
    }

    overtime_minutes = 0
    late_minutes = 0    # PRESENT days only (a late half day is already a half day)
    warnings = []   # anything here sets requires_review
    notes = []      # informational only

    first_no_shift = None
    first_not_evaluated = None

    def _is_unevaluated(day, rec):
        """Today/future day with nothing finished to evaluate yet."""
        if today is None or day < today:
            return False
        return rec is None or rec.status in REVIEW_STATUSES

    def _handle_missing(day):
        if missing_action == "SKIP":
            sources["missing_record_skipped"] += ONE
            warnings.append(
                f"No attendance record on {day}; skipped (no deduction)."
            )
        elif missing_action == "ABSENT":
            counts["absent_days"] += ONE
            sources["missing_record_absent"] += ONE
            warnings.append(
                f"No attendance record on {day}; treated as absent."
            )
        else:
            sources["held_for_review_days"] += ONE
            warnings.append(
                f"No attendance record on {day}; held for review."
            )

    current = period_start
    while current <= period_end:
        # ---- 0. Outside employment window ----
        if (
            (joining_date and current < joining_date)
            or (exit_date and current > exit_date)
        ):
            counts["not_employed_days"] += ONE
            if fallback_day_info is not None:
                fcal = fallback_day_info(current)
                ftype = fcal.get("day_type")
                if ftype == "WORKING_DAY" or (
                    ftype == "HOLIDAY" and fcal.get("pay_type") == "UNPAID"
                ):
                    counts["not_employed_working_days"] += ONE
            current += timedelta(days=1)
            continue

        cal = day_info(current)
        day_type = cal.get("day_type")
        pay_type = cal.get("pay_type")
        rec = records.get(current)
        worked = rec is not None and rec.status in WORKED_STATUSES

        # ---- 1. Paid holiday: day off ----
        if day_type == "HOLIDAY" and pay_type != "UNPAID":
            counts["holiday_days"] += ONE
            sources["paid_holiday_days"] += ONE
            if worked:
                sources["worked_on_off_days"] += ONE
                notes.append(f"{current}: worked on a paid holiday (no extra pay).")
            current += timedelta(days=1)
            continue

        # ---- 2. Weekly off: day off ----
        if day_type == "WEEKLY_OFF":
            counts["weekly_off_days"] += ONE
            if worked:
                sources["worked_on_off_days"] += ONE
                notes.append(f"{current}: worked on a weekly off (no extra pay).")
            current += timedelta(days=1)
            continue

        # ---- 3. No shift assigned ----
        if day_type == "NO_SHIFT_ASSIGNED":
            if rec is None and current not in leave_map:
                sources["no_shift_days_not_counted"] += ONE
                if first_no_shift is None:
                    first_no_shift = current
                current += timedelta(days=1)
                continue
            # The employee has data for the day: count it as a working day.
            sources["no_shift_days_with_record"] += ONE

        # ---- 4. Working day (also: unpaid holiday) ----
        if day_type == "HOLIDAY" and pay_type == "UNPAID":
            sources["unpaid_holiday_as_working_days"] += ONE

        counts["working_days"] += ONE

        if rec is None:
            if current in leave_map:
                # Approved leave but no attendance row was written for it.
                if leave_map[current]:
                    counts["paid_leave_days"] += ONE
                else:
                    counts["unpaid_leave_days"] += ONE
                    sources["unpaid_leave_absorbed_into_absent"] += ONE
                sources["leave_without_record"] += ONE
            elif _is_unevaluated(current, rec):
                sources["not_evaluated_days"] += ONE
                if first_not_evaluated is None:
                    first_not_evaluated = current
            else:
                _handle_missing(current)
            current += timedelta(days=1)
            continue

        status = rec.status

        if status == "PRESENT":
            counts["present_days"] += ONE
            overtime_minutes += rec.overtime_minutes or 0
            late_minutes += getattr(rec, "late_minutes", 0) or 0

        elif status == "HALF_DAY":
            counts["half_days"] += ONE
            overtime_minutes += rec.overtime_minutes or 0

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

        elif status in REVIEW_STATUSES:
            if _is_unevaluated(current, rec):
                # Today, still open (checked in, not out yet).
                sources["not_evaluated_days"] += ONE
                if first_not_evaluated is None:
                    first_not_evaluated = current
            else:
                sources["held_for_review_days"] += ONE
                warnings.append(
                    f"{current}: attendance {status.lower()}; "
                    f"held for review (no deduction)."
                )

        else:
            sources["held_for_review_days"] += ONE
            warnings.append(
                f"{current}: unrecognised attendance status "
                f"'{status}'; held for review."
            )

        current += timedelta(days=1)

    # ---- Period-level warnings (force review so the admin looks) ----
    if first_no_shift is not None:
        warnings.append(
            f"No shift assigned on {int(sources['no_shift_days_not_counted'])} "
            f"day(s) (first: {first_no_shift}); those days are not counted. "
            f"Assign a shift to this employee."
        )

    if counts["not_employed_days"] > ZERO:
        warnings.append(
            f"Employee not employed on {int(counts['not_employed_days'])} "
            f"day(s) of this period (joining date {joining_date}, "
            f"resignation date {exit_date}); those days are unpaid."
        )

    if first_not_evaluated is not None:
        warnings.append(
            f"{int(sources['not_evaluated_days'])} day(s) on or after "
            f"{first_not_evaluated} have no finished attendance yet and were "
            f"not evaluated. Generate again after the period ends."
        )

    requires_review = bool(warnings)

    return {
        "counts": counts,
        "overtime_minutes": overtime_minutes,
        "late_minutes": late_minutes,
        "warnings": warnings,
        "notes": notes,
        "requires_review": requires_review,
        "sources": sources,
    }


# =========================================================
# DATABASE WRAPPER
# =========================================================

def _find_fallback_shift(employee, organization, period_start, period_end):
    """
    Shift used only to decide which not-employed days would have been working
    days: the first assignment overlapping the period, else the latest one.
    """
    base = EmployeeShiftAssignment.objects.filter(
        organization=organization,
        employee=employee,
        shift__is_active=True,
    ).select_related("shift")

    overlapping = (
        base.filter(effective_from__lte=period_end)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=period_start))
        .order_by("effective_from")
        .first()
    )
    if overlapping:
        return overlapping.shift

    latest = base.order_by("-effective_from").first()
    return latest.shift if latest else None


def compute_attendance_counts(
    employee, organization, period_start, period_end, settings,
):
    """
    Walk the period day by day and classify each day.

    Returns dict with:
      counts, overtime_minutes, warnings, notes, requires_review, sources.
    """
    records = {
        r.work_date: r
        for r in AttendanceRecord.objects.filter(
            organization=organization,
            employee=employee,
            work_date__range=(period_start, period_end),
        ).only("work_date", "status", "overtime_minutes", "late_minutes")
    }

    leave_map = build_leave_map(employee, period_start, period_end)

    joining_date = getattr(employee, "joining_date", None)
    exit_date = getattr(employee, "resignation_date", None)

    def day_info(day):
        shift = get_employee_shift(employee, organization, day)
        return get_calendar_day(
            organization=organization,
            target_date=day,
            shift=shift,
        )

    fallback_day_info = None
    needs_fallback = (
        (joining_date and joining_date > period_start)
        or (exit_date and exit_date < period_end)
    )
    if needs_fallback:
        fallback_shift = _find_fallback_shift(
            employee, organization, period_start, period_end,
        )
        if fallback_shift is not None:
            def fallback_day_info(day):
                return get_calendar_day(
                    organization=organization,
                    target_date=day,
                    shift=fallback_shift,
                )

    return classify_period(
        period_start,
        period_end,
        day_info=day_info,
        records=records,
        leave_map=leave_map,
        missing_action=settings.missing_attendance_action,
        joining_date=joining_date,
        exit_date=exit_date,
        today=timezone.localdate(),
        fallback_day_info=fallback_day_info,
    )
