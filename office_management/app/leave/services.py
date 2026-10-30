from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from app.employees.models import Employee

from .models import (
    LeaveType,
    EmployeeLeaveBalance,
    LeaveApplication,
    LeaveBalanceTransaction,
)


ZERO = Decimal("0.00")
ONE = Decimal("1.00")


# =========================================================
# COMMON HELPERS
# =========================================================

def create_leave_transaction(
    balance,
    transaction_type,
    days,
    created_by=None,
    leave_application=None,
    remarks="",
):
    return LeaveBalanceTransaction.objects.create(
        organization=balance.organization,
        employee=balance.employee,
        leave_type=balance.leave_type,
        leave_balance=balance,
        leave_application=leave_application,
        transaction_type=transaction_type,
        days=days,
        remarks=remarks,
        created_by=created_by,
    )


def get_employee_for_leave(employee_id, organization):
    employee = Employee.objects.filter(
        id=employee_id,
        organization=organization,
        is_active=True,
        employment_status="ACTIVE",
    ).first()

    if not employee:
        raise ValueError("Employee not found or inactive.")

    return employee


# =========================================================
# LEAVE BALANCE
# =========================================================

@transaction.atomic
def get_or_create_leave_balance(
    employee,
    leave_type,
    leave_year,
    created_by=None,
):
    if employee.organization_id != leave_type.organization_id:
        raise ValueError(
            "Employee and leave type must belong to the same organization."
        )

    balance, created = EmployeeLeaveBalance.objects.get_or_create(
        organization=employee.organization,
        employee=employee,
        leave_type=leave_type,
        leave_year=leave_year,
        defaults={
            "opening_balance": ZERO,
            "allocated_days": leave_type.annual_allocation,
            "used_days": ZERO,
            "pending_days": ZERO,
        },
    )

    if created:
        if leave_type.annual_allocation > ZERO:
            create_leave_transaction(
                balance=balance,
                transaction_type="ALLOCATION",
                days=leave_type.annual_allocation,
                created_by=created_by,
                remarks=f"Annual allocation for {leave_year}.",
            )

    return balance


@transaction.atomic
def initialize_leave_balances(
    organization,
    leave_year,
    leave_type_ids=None,
    created_by=None,
):
    """
    Initialize yearly balances for all active employees
    and selected active leave types.

    Existing balances are not overwritten.
    """

    employees = Employee.objects.filter(
        organization=organization,
        is_active=True,
        employment_status="ACTIVE",
    )

    leave_types = LeaveType.objects.filter(
        organization=organization,
        is_active=True,
    )

    if leave_type_ids:
        leave_types = leave_types.filter(id__in=leave_type_ids)

    created_count = 0
    existing_count = 0

    for employee in employees.iterator():
        for leave_type in leave_types.iterator():
            _, created = get_or_create_leave_balance(
                employee=employee,
                leave_type=leave_type,
                leave_year=leave_year,
                created_by=created_by,
            )

            if created:
                created_count += 1
            else:
                existing_count += 1

    return {
        "created": created_count,
        "existing": existing_count,
    }


# =========================================================
# CALCULATE LEAVE DAYS
# =========================================================

def calculate_leave_days(
    employee,
    organization,
    start_date,
    end_date,
):
    """
    Count only working days.

    Existing Calendar service determines holidays and weekly offs.
    Existing Attendance service determines the employee's assigned shift.

    Employees without an assigned shift are treated as working
    unless an active organization holiday exists.
    """

    from app.attendance.services import get_employee_shift
    from app.calendar_app.services import get_calendar_day
    from app.calendar_app.models import CalendarHoliday

    yearly_days = defaultdict(lambda: ZERO)

    current_date = start_date

    while current_date <= end_date:

        shift = get_employee_shift(
            employee=employee,
            organization=organization,
            work_date=current_date,
        )

        # No shift assigned: working day unless it is a holiday.
        if shift is None:

            is_holiday = CalendarHoliday.objects.filter(
                organization=organization,
                date=current_date,
                is_active=True,
            ).exists()

            if not is_holiday:
                yearly_days[current_date.year] += ONE

            current_date += timedelta(days=1)
            continue

        calendar_day = get_calendar_day(
            organization=organization,
            target_date=current_date,
            shift=shift,
        )

        if calendar_day.get("is_working_day"):
            yearly_days[current_date.year] += ONE

        current_date += timedelta(days=1)

    total_days = sum(yearly_days.values(), ZERO)

    if total_days <= ZERO:
        raise ValueError(
            "The selected date range does not contain any working days."
        )

    return dict(yearly_days)


# =========================================================
# CREATE LEAVE APPLICATION
# =========================================================

@transaction.atomic
def create_leave_application(
    employee,
    organization,
    leave_type,
    start_date,
    end_date,
    reason,
    created_by=None,
):
    if employee.organization_id != organization.id:
        raise ValueError("Employee does not belong to this organization.")

    if leave_type.organization_id != organization.id:
        raise ValueError("Leave type does not belong to this organization.")

    if not employee.is_active or employee.employment_status != "ACTIVE":
        raise ValueError("Only active employees can apply for leave.")

    if not leave_type.is_active:
        raise ValueError("This leave type is inactive.")

    if end_date < start_date:
        raise ValueError("End date cannot be before start date.")

    # Cross-year applications are not allowed.
    if start_date.year != end_date.year:
        raise ValueError(
            "Leave applications cannot span multiple calendar years. "
            "Please submit separate applications for each year."
        )

    if start_date < timezone.localdate():
        raise ValueError("Leave cannot be applied for past dates.")

    if not reason or not reason.strip():
        raise ValueError("Leave reason is required.")

    # Prevent overlapping pending or approved applications.
    overlapping = LeaveApplication.objects.filter(
        organization=organization,
        employee=employee,
        status__in=["PENDING", "APPROVED"],
        start_date__lte=end_date,
        end_date__gte=start_date,
    ).exists()

    if overlapping:
        raise ValueError(
            "You already have a pending or approved leave application "
            "for some dates in this range."
        )

    # Prevent leave application for dates with existing attendance.
    from app.attendance.models import AttendanceRecord

    existing_attendance = AttendanceRecord.objects.filter(
        organization=organization,
        employee=employee,
        work_date__range=(start_date, end_date),
        check_in__isnull=False,
    ).exists()

    if existing_attendance:
        raise ValueError(
            "Attendance already exists for one or more dates in this range."
        )

    # Calculate working days.
    yearly_days = calculate_leave_days(
        employee=employee,
        organization=organization,
        start_date=start_date,
        end_date=end_date,
    )

    total_days = sum(yearly_days.values(), ZERO)

    # Create or retrieve the relevant yearly balances.
    balances = []

    for leave_year in sorted(yearly_days):
        balance = get_or_create_leave_balance(
            employee=employee,
            leave_type=leave_type,
            leave_year=leave_year,
            created_by=created_by,
        )
        balances.append((balance, yearly_days[leave_year]))

    # Lock balances in consistent order to prevent concurrent overbooking.
    locked_balances = {
        balance.id: balance
        for balance in EmployeeLeaveBalance.objects.select_for_update()
        .filter(id__in=[item[0].id for item in balances])
        .order_by("id")
    }

    for original_balance, requested_days in balances:
        balance = locked_balances[original_balance.id]

        if balance.available < requested_days:
            raise ValueError(
                f"Insufficient {leave_type.name} balance for "
                f"{balance.leave_year}. Available: {balance.available}, "
                f"requested: {requested_days}."
            )

    application = LeaveApplication.objects.create(
        organization=organization,
        employee=employee,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        total_days=total_days,
        reason=reason.strip(),
        status="PENDING",
    )

    # Reserve pending balance.
    for original_balance, requested_days in balances:
        balance = locked_balances[original_balance.id]

        balance.pending_days += requested_days
        balance.save(
            update_fields=[
                "pending_days",
                "updated_at",
            ]
        )

        create_leave_transaction(
            balance=balance,
            transaction_type="PENDING_RESERVE",
            days=requested_days,
            created_by=created_by,
            leave_application=application,
            remarks="Leave application submitted.",
        )

    return application


# =========================================================
# APPLY APPROVED LEAVE TO ATTENDANCE
# =========================================================

@transaction.atomic
def apply_leave_to_attendance(application):
    """
    Mark approved leave as ON_LEAVE on working days only.
    Employee employment_status is never modified.
    """

    from app.attendance.models import AttendanceRecord
    from app.attendance.services import (
        get_employee_shift,
        get_or_create_attendance,
    )

    from app.calendar_app.models import CalendarHoliday
    from app.calendar_app.services import get_calendar_day

    current_date = application.start_date

    while current_date <= application.end_date:

        shift = get_employee_shift(
            employee=application.employee,
            organization=application.organization,
            work_date=current_date,
        )

        # Match calculate_leave_days: no shift + not holiday = working day.
        if shift is None:
            is_holiday = CalendarHoliday.objects.filter(
                organization=application.organization,
                date=current_date,
                is_active=True,
            ).exists()
            is_working = not is_holiday
        else:
            calendar_day = get_calendar_day(
                organization=application.organization,
                target_date=current_date,
                shift=shift,
            )
            is_working = bool(calendar_day.get("is_working_day"))

        if not is_working:
            current_date += timedelta(days=1)
            continue

        attendance = get_or_create_attendance(
            employee=application.employee,
            organization=application.organization,
            work_date=current_date,
        )

        if attendance.check_in:
            raise ValueError(
                f"Employee already checked in on {current_date}. "
                "Approved leave cannot overwrite attendance."
            )

        attendance.status = "ON_LEAVE"
        attendance.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        current_date += timedelta(days=1)


# =========================================================
# REVIEW LEAVE APPLICATION
# =========================================================

@transaction.atomic
def review_leave_application(
    application_id,
    organization,
    reviewed_by,
    approve,
    review_remarks="",
):
    application = LeaveApplication.objects.select_for_update().filter(
        id=application_id,
        organization=organization,
    ).first()

    if not application:
        raise ValueError("Leave application not found.")

    if application.status != "PENDING":
        raise ValueError(
            f"Application has already been {application.status.lower()}."
        )

    reserve_transactions = list(
        LeaveBalanceTransaction.objects.filter(
            leave_application=application,
            transaction_type="PENDING_RESERVE",
        ).select_related("leave_balance")
    )

    if not reserve_transactions:
        raise ValueError("Leave balance reservation was not found.")

    balance_ids = [
        item.leave_balance_id
        for item in reserve_transactions
    ]

    locked_balances = {
        balance.id: balance
        for balance in EmployeeLeaveBalance.objects.select_for_update()
        .filter(id__in=balance_ids)
        .order_by("id")
    }

    for reserve in reserve_transactions:
        balance = locked_balances[reserve.leave_balance_id]
        days = reserve.days

        if balance.pending_days < days:
            raise ValueError("Invalid pending leave balance.")

        balance.pending_days -= days

        if approve:
            balance.used_days += days

        balance.save(
            update_fields=[
                "pending_days",
                "used_days",
                "updated_at",
            ]
        )

        create_leave_transaction(
            balance=balance,
            transaction_type="APPROVAL" if approve else "REJECTION",
            days=days if approve else -days,
            created_by=reviewed_by,
            leave_application=application,
            remarks=(
                "Leave application approved."
                if approve
                else "Leave application rejected."
            ),
        )

    application.status = "APPROVED" if approve else "REJECTED"
    application.reviewed_by = reviewed_by
    application.reviewed_at = timezone.now()
    application.review_remarks = review_remarks or ""

    application.save(
        update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_remarks",
            "updated_at",
        ]
    )

    if approve:
        apply_leave_to_attendance(application)

    return application


# =========================================================
# CHECK APPROVED LEAVE
# =========================================================

def has_approved_leave(employee, work_date):
    return LeaveApplication.objects.filter(
        employee=employee,
        status="APPROVED",
        start_date__lte=work_date,
        end_date__gte=work_date,
    ).exists()


# =========================================================
# CANCEL LEAVE APPLICATION
# =========================================================

@transaction.atomic
def cancel_leave_application(
    application_id,
    organization,
    cancelled_by,
    employee=None,
):
    application = LeaveApplication.objects.select_for_update().filter(
        id=application_id,
        organization=organization,
    ).first()

    if not application:
        raise ValueError("Leave application not found.")

    if employee and application.employee_id != employee.id:
        raise ValueError("You cannot cancel another employee's application.")

    if application.status not in ["PENDING", "APPROVED"]:
        raise ValueError(
            "Only pending or approved applications can be cancelled."
        )

    reserve_transactions = list(
        LeaveBalanceTransaction.objects.filter(
            leave_application=application,
            transaction_type="PENDING_RESERVE",
        ).select_related("leave_balance")
    )

    if not reserve_transactions:
        raise ValueError("Leave balance reservation was not found.")

    balance_ids = [
        item.leave_balance_id
        for item in reserve_transactions
    ]

    locked_balances = {
        balance.id: balance
        for balance in EmployeeLeaveBalance.objects.select_for_update()
        .filter(id__in=balance_ids)
        .order_by("id")
    }

    was_approved = application.status == "APPROVED"

    for reserve in reserve_transactions:
        balance = locked_balances[reserve.leave_balance_id]
        days = reserve.days

        if was_approved:
            if balance.used_days < days:
                raise ValueError("Invalid used leave balance.")

            balance.used_days -= days
        else:
            if balance.pending_days < days:
                raise ValueError("Invalid pending leave balance.")

            balance.pending_days -= days

        balance.save(
            update_fields=[
                "pending_days",
                "used_days",
                "updated_at",
            ]
        )

        create_leave_transaction(
            balance=balance,
            transaction_type="CANCELLATION",
            days=-days,
            created_by=cancelled_by,
            leave_application=application,
            remarks=(
                "Approved leave cancelled."
                if was_approved
                else "Pending leave application cancelled."
            ),
        )

    if was_approved:
        from app.attendance.models import AttendanceRecord

        attendance_records = AttendanceRecord.objects.filter(
            organization=organization,
            employee=application.employee,
            work_date__range=(
                application.start_date,
                application.end_date,
            ),
            status="ON_LEAVE",
        )

        if attendance_records.filter(check_in__isnull=False).exists():
            raise ValueError(
                "Cannot cancel approved leave because attendance "
                "has already been recorded for one or more leave dates."
            )

        # Reset to INCOMPLETE. The absence scheduler can subsequently
        # evaluate these dates under the normal attendance rules.
        attendance_records.update(status="INCOMPLETE")

    application.status = "CANCELLED"

    application.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    return application


# =========================================================
# MANUAL BALANCE ADJUSTMENT
# =========================================================

@transaction.atomic
def adjust_leave_balance(
    balance_id,
    organization,
    days,
    created_by,
    remarks="",
):
    days = Decimal(str(days))

    if days == ZERO:
        raise ValueError("Adjustment days cannot be zero.")

    balance = EmployeeLeaveBalance.objects.select_for_update().filter(
        id=balance_id,
        organization=organization,
    ).first()

    if not balance:
        raise ValueError("Leave balance not found.")

    new_allocation = balance.allocated_days + days

    if new_allocation < ZERO:
        raise ValueError("Allocated balance cannot become negative.")

    if (
        balance.opening_balance
        + new_allocation
        - balance.used_days
        - balance.pending_days
    ) < ZERO:
        raise ValueError(
            "Adjustment would make available leave balance negative."
        )

    balance.allocated_days = new_allocation

    balance.save(
        update_fields=[
            "allocated_days",
            "updated_at",
        ]
    )

    create_leave_transaction(
        balance=balance,
        transaction_type="ADJUSTMENT",
        days=days,
        created_by=created_by,
        remarks=remarks or "Manual leave balance adjustment.",
    )

    return balance
