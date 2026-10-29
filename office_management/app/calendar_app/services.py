from datetime import timedelta

from django.db.models import Q

from .models import WeeklyOffRule, CalendarHoliday
from app.attendance.models import EmployeeShiftAssignment


# =========================================================
# GET CALENDAR DAY
# =========================================================

def get_calendar_day(organization, target_date, shift=None):
    """
    Resolve a date for an organization and optional shift.

    Precedence:
    1. Active organization holiday
    2. Applicable shift weekly off
    3. Working day, if a shift is assigned
    4. No shift assigned
    """

    holiday = CalendarHoliday.objects.filter(
        organization=organization,
        date=target_date,
        is_active=True,
    ).first()

    shift_data = {
        "shift_id": shift.id if shift else None,
        "shift_name": shift.name if shift else None,
        "shift_start_time": shift.start_time if shift else None,
        "shift_end_time": shift.end_time if shift else None,
    }

    if holiday:
        return {
            "date": target_date,
            "day_type": "HOLIDAY",
            "is_working_day": False,
            **shift_data,
            "holiday_name": holiday.name,
            "holiday_type": holiday.holiday_type,
            "pay_type": holiday.pay_type,
            "is_optional": holiday.is_optional,
            "weekly_off_rule_id": None,
            "week_of_month": None,
        }

    if shift is None:
        return {
            "date": target_date,
            "day_type": "NO_SHIFT_ASSIGNED",
            "is_working_day": False,
            **shift_data,
            "holiday_name": None,
            "holiday_type": None,
            "pay_type": None,
            "is_optional": False,
            "weekly_off_rule_id": None,
            "week_of_month": None,
        }

    if shift.organization_id != organization.id:
        raise ValueError(
            "The selected shift does not belong to this organization."
        )

    day_of_week = target_date.weekday()
    occurrence = ((target_date.day - 1) // 7) + 1

    rules = WeeklyOffRule.objects.filter(
        shift=shift,
        day_of_week=day_of_week,
        is_active=True,
        effective_from__lte=target_date,
    ).filter(
        Q(effective_to__isnull=True)
        | Q(effective_to__gte=target_date)
    ).filter(
        Q(week_of_month__isnull=True)
        | Q(week_of_month=occurrence)
    )

    # Prefer a specific weekday occurrence over an every-week rule.
    rule = rules.order_by(
        "-week_of_month",
        "-effective_from",
    ).first()

    if rule:
        return {
            "date": target_date,
            "day_type": "WEEKLY_OFF",
            "is_working_day": False,
            **shift_data,
            "holiday_name": None,
            "holiday_type": None,
            "pay_type": None,
            "is_optional": False,
            "weekly_off_rule_id": rule.id,
            "week_of_month": rule.week_of_month,
        }

    return {
        "date": target_date,
        "day_type": "WORKING_DAY",
        "is_working_day": True,
        **shift_data,
        "holiday_name": None,
        "holiday_type": None,
        "pay_type": None,
        "is_optional": False,
        "weekly_off_rule_id": None,
        "week_of_month": None,
    }


# =========================================================
# GET EMPLOYEE CALENDAR
# =========================================================

def get_employee_calendar(organization, employee, date_from, date_to):
    assignments = EmployeeShiftAssignment.objects.filter(
        organization=organization,
        employee=employee,
        effective_from__lte=date_to,
    ).filter(
        Q(effective_to__isnull=True) |
        Q(effective_to__gte=date_from)
    ).select_related("shift").order_by("-effective_from")

    assignments = list(assignments)
    calendar = []

    current_date = date_from

    while current_date <= date_to:
        applicable_assignment = next(
            (
                assignment
                for assignment in assignments
                if assignment.effective_from <= current_date
                and (
                    assignment.effective_to is None
                    or assignment.effective_to >= current_date
                )
            ),
            None,
        )

        shift = (
            applicable_assignment.shift
            if applicable_assignment
            else None
        )

        day_data = get_calendar_day(
            organization=organization,
            target_date=current_date,
            shift=shift,
        )

        calendar.append(day_data)
        current_date += timedelta(days=1)

    return calendar
