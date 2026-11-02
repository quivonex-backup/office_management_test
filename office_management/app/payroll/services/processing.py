"""
Persistence, generation, finalization, manual deduction updates,
bulk salary assignment, and single-record recompute.

Imports common + computation only. No cycle back to payments.
"""

from datetime import date as date_type
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from app.employees.models import Employee

from ..models import (
    SalaryStructure,
    EmployeeSalaryAssignment,
    PayrollRun,
    PayrollRecord,
    PayrollLineItem,
)
from .common import (
    ZERO,
    PAYROLL_ELIGIBLE_STATUSES,
    q2,
    audit_log,
)
from .computation import compute_payslip_data


# =========================================================
# PERSISTENCE HELPERS
# =========================================================

def _persist_payroll_record(payroll_run, employee, data):
    line_items_data = data.pop("line_items", [])
    data.pop("warnings", None)

    record = PayrollRecord.objects.create(
        payroll_run=payroll_run,
        organization=payroll_run.organization,
        employee=employee,
        present_days=data["present_days"],
        half_days=data["half_days"],
        absent_days=data["absent_days"],
        paid_leave_days=data["paid_leave_days"],
        unpaid_leave_days=data["unpaid_leave_days"],
        holiday_days=data["holiday_days"],
        weekly_off_days=data["weekly_off_days"],
        overtime_hours=data["overtime_hours"],
        monthly_salary=data["monthly_salary"],
        per_day_rate=data["per_day_rate"],
        pf_employee=data["pf_employee"],
        pf_employer=data["pf_employer"],
        eps=data["eps"],
        edli=data["edli"],
        esi_employee=data["esi_employee"],
        esi_employer=data["esi_employer"],
        pt=data["pt"],
        tds=data["tds"],
        lwf_employee=data["lwf_employee"],
        lwf_employer=data["lwf_employer"],
        other_deductions=data["other_deductions"],
        gross_earnings=data["gross_earnings"],
        total_deductions=data["total_deductions"],
        net=data["net"],
        generation_status="GENERATED",
        requires_review=data["requires_review"],
        breakdown=data["breakdown"],
    )

    for item in line_items_data:
        PayrollLineItem.objects.create(
            payroll_record=record,
            component_code=item["component_code"],
            component_name=item["component_name"],
            component_type=item["component_type"],
            amount=item["amount"],
            calculation_details=item.get("calculation_details", {}),
        )

    return record


def _persist_skipped_record(payroll_run, employee, reason):
    return PayrollRecord.objects.create(
        payroll_run=payroll_run,
        organization=payroll_run.organization,
        employee=employee,
        generation_status="SKIPPED",
        generation_notes=reason,
    )


def _persist_error_record(payroll_run, employee, reason):
    return PayrollRecord.objects.create(
        payroll_run=payroll_run,
        organization=payroll_run.organization,
        employee=employee,
        generation_status="ERROR",
        generation_notes=reason,
        requires_review=True,
        review_notes=reason,
    )


def _roll_up_totals(payroll_run):
    """Recompute run-level totals from GENERATED records only."""
    records = payroll_run.records.filter(generation_status="GENERATED")

    total_employees = records.count()
    total_gross = ZERO
    total_deductions = ZERO
    total_net = ZERO

    for r in records.iterator():
        total_gross += r.gross_earnings
        total_deductions += r.total_deductions
        total_net += r.net

    payroll_run.total_employees = total_employees
    payroll_run.total_gross = q2(total_gross)
    payroll_run.total_deductions = q2(total_deductions)
    payroll_run.total_net = q2(total_net)
    payroll_run.save(
        update_fields=[
            "total_employees",
            "total_gross",
            "total_deductions",
            "total_net",
            "updated_at",
        ]
    )
    return payroll_run


# =========================================================
# PAYROLL GENERATION
# =========================================================

@transaction.atomic
def generate_payroll(payroll_run, generated_by=None):
    """
    Generate payroll records for a DRAFT run.

    Guard: reject generation when ANY finalised payroll run already covers
    an overlapping period. This closes the double-payment hole where two
    parallel runs both generate before either is paid, then both finalise
    and both pay.
    """
    if payroll_run.status != "DRAFT":
        raise ValueError(
            f"Only DRAFT runs can be generated. "
            f"This run is {payroll_run.status}."
        )

    if payroll_run.records.exists():
        raise ValueError(
            "This run already has records. Use a fresh run or "
            "clear this one before regenerating."
        )

    organization = payroll_run.organization
    period_start = payroll_run.period_start
    period_end = payroll_run.period_end

    # ---- Guard: block overlap with any FINALIZED run ----
    overlapping_finalized = (
        PayrollRun.objects.filter(
            organization=organization,
            status="FINALIZED",
            period_start__lte=period_end,
            period_end__gte=period_start,
        )
        .exclude(pk=payroll_run.pk)
        .order_by("period_start")
    )

    if overlapping_finalized.exists():
        conflict = overlapping_finalized.first()
        raise ValueError(
            f"Cannot generate this run: a finalized payroll run already "
            f"exists for an overlapping period "
            f"({conflict.period_start} to {conflict.period_end}, "
            f"id={conflict.id}). Correction runs must use a non-overlapping "
            f"period, or the existing run must be reversed first."
        )

    # ---- Proceed with normal generation ----
    employees = (
        Employee.objects.filter(
            organization=organization,
            is_active=True,
            employment_status__in=PAYROLL_ELIGIBLE_STATUSES,
        )
        .select_related("work_state")
        .order_by("id")
    )

    errors = []
    generated_count = 0
    skipped_count = 0

    for employee in employees.iterator():
        try:
            data = compute_payslip_data(
                employee=employee,
                organization=organization,
                period_start=period_start,
                period_end=period_end,
            )
        except ValueError as exc:
            message = str(exc)

            if message.startswith("No salary assignment found"):
                _persist_skipped_record(payroll_run, employee, message)
                skipped_count += 1
            else:
                _persist_error_record(payroll_run, employee, message)
                errors.append({
                    "employee_id": employee.id,
                    "employee_code": employee.employee_code,
                    "message": message,
                })
            continue

        _persist_payroll_record(payroll_run, employee, data)
        generated_count += 1

    _roll_up_totals(payroll_run)

    payroll_run.status = "GENERATED"
    payroll_run.save(update_fields=["status", "updated_at"])

    audit_log(
        user=generated_by,
        action="GENERATE",
        module="payroll",
        object_type="PayrollRun",
        object_id=payroll_run.id,
        description=(
            f"Payroll generated: {generated_count} generated, "
            f"{skipped_count} skipped, {len(errors)} errors."
        ),
    )

    return {
        "payroll_run": payroll_run,
        "generated_count": generated_count,
        "skipped_count": skipped_count,
        "error_count": len(errors),
        "errors": errors,
    }


# =========================================================
# FINALIZATION
# =========================================================

@transaction.atomic
def finalize_payroll(payroll_run, finalized_by=None):
    """
    Lock a GENERATED run. Only FINALIZED runs are eligible for payment.

    Blocks finalization when:
      - any record has generation_status="ERROR"
      - any GENERATED record still has requires_review=True

    The admin must resolve review-flagged records (via recompute after
    fixing attendance, or by acknowledging them with review_notes) before
    the run can be finalized. This prevents silent payment of unverified
    days when missing_attendance_action="REVIEW".
    """
    payroll_run = PayrollRun.objects.select_for_update().get(pk=payroll_run.pk)

    if payroll_run.status != "GENERATED":
        raise ValueError(
            f"Only GENERATED runs can be finalized. "
            f"This run is {payroll_run.status}."
        )

    error_count = payroll_run.records.filter(
        generation_status="ERROR"
    ).count()

    if error_count > 0:
        raise ValueError(
            f"Cannot finalize: {error_count} record(s) have generation "
            f"errors. Fix the underlying issues and regenerate, or remove "
            f"those employees from the run."
        )

    review_records = payroll_run.records.filter(
        generation_status="GENERATED",
        requires_review=True,
    ).select_related("employee").order_by("employee__employee_code")

    review_count = review_records.count()

    if review_count > 0:
        flagged = [
            {
                "record_id": r.id,
                "employee_code": r.employee.employee_code,
            }
            for r in review_records[:20]
        ]
        raise ValueError(
            f"Cannot finalize: {review_count} record(s) still require "
            f"review. Resolve each flagged record by (a) correcting "
            f"attendance and calling recompute on the record, or "
            f"(b) acknowledging the record via records/update-deductions "
            f"with review_notes. Flagged records: {flagged}"
        )

    _roll_up_totals(payroll_run)

    payroll_run.status = "FINALIZED"
    payroll_run.finalized_by = finalized_by
    payroll_run.finalized_at = timezone.now()
    payroll_run.save(
        update_fields=[
            "status", "finalized_by", "finalized_at", "updated_at",
        ]
    )

    audit_log(
        user=finalized_by,
        action="FINALIZE",
        module="payroll",
        object_type="PayrollRun",
        object_id=payroll_run.id,
        description="Payroll run finalized.",
    )

    return payroll_run


# =========================================================
# RECOMPUTE SINGLE RECORD
# =========================================================

def _recompute_record_totals_from_line_items(record):
    """Rebuild gross/deductions/net from PayrollLineItem rows."""
    agg = record.line_items.values("component_type").annotate(
        total=Sum("amount")
    )

    gross = ZERO
    deductions = ZERO

    for row in agg:
        ctype = row["component_type"]
        total = row["total"] or ZERO
        if ctype == "EARNING":
            gross += total
        elif ctype in {"DEDUCTION", "LOP"}:
            deductions += total

    record.gross_earnings = q2(gross)
    record.total_deductions = q2(deductions)
    record.net = q2(record.gross_earnings - record.total_deductions)
    record.save(
        update_fields=[
            "gross_earnings", "total_deductions", "net", "updated_at",
        ]
    )


@transaction.atomic
def recompute_payroll_record(record, recomputed_by=None):
    """
    Re-run compute_payslip_data for one record and overwrite it in place.

    - Preserves record.tds, record.other_deductions, record.review_notes
      as manual deductions on top of the fresh computation.
    - Rebuilds PayrollLineItem rows for the record.
    - Rolls up parent run totals.
    - Record identity (PayrollRecord.id, payroll_run_id) unchanged.

    Allowed only when:
      - parent run status is DRAFT or GENERATED (not FINALIZED)
      - record.generation_status is GENERATED (not SKIPPED or ERROR)
      - no payments recorded against this record
    """
    if record.payroll_run.status == "FINALIZED":
        raise ValueError(
            "Cannot recompute a record on a finalized payroll run."
        )

    if record.generation_status != "GENERATED":
        raise ValueError(
            "Only GENERATED records can be recomputed."
        )

    if record.payments.exists():
        raise ValueError(
            "Cannot recompute a record after a payment has been recorded."
        )

    # Capture manual fields before the re-run.
    preserved_tds = record.tds
    preserved_other = record.other_deductions
    preserved_review_notes = record.review_notes

    # Re-run the calculation.
    data = compute_payslip_data(
        employee=record.employee,
        organization=record.organization,
        period_start=record.payroll_run.period_start,
        period_end=record.payroll_run.period_end,
    )

    line_items_data = data.pop("line_items", [])
    data.pop("warnings", None)

    # Overwrite model fields from the fresh computation.
    record.present_days = data["present_days"]
    record.half_days = data["half_days"]
    record.absent_days = data["absent_days"]
    record.paid_leave_days = data["paid_leave_days"]
    record.unpaid_leave_days = data["unpaid_leave_days"]
    record.holiday_days = data["holiday_days"]
    record.weekly_off_days = data["weekly_off_days"]
    record.overtime_hours = data["overtime_hours"]
    record.monthly_salary = data["monthly_salary"]
    record.per_day_rate = data["per_day_rate"]
    record.pf_employee = data["pf_employee"]
    record.pf_employer = data["pf_employer"]
    record.eps = data["eps"]
    record.edli = data["edli"]
    record.esi_employee = data["esi_employee"]
    record.esi_employer = data["esi_employer"]
    record.pt = data["pt"]
    record.lwf_employee = data["lwf_employee"]
    record.lwf_employer = data["lwf_employer"]
    record.requires_review = data["requires_review"]
    record.breakdown = data["breakdown"]

    # Restore manual deductions and review note from before.
    record.tds = preserved_tds
    record.other_deductions = preserved_other
    record.review_notes = preserved_review_notes

    record.generation_notes = None

    record.save()

    # Replace line items: delete all, re-insert fresh, then re-append manual.
    record.line_items.all().delete()

    for item in line_items_data:
        PayrollLineItem.objects.create(
            payroll_record=record,
            component_code=item["component_code"],
            component_name=item["component_name"],
            component_type=item["component_type"],
            amount=item["amount"],
            calculation_details=item.get("calculation_details", {}),
        )

    if preserved_tds and preserved_tds > ZERO:
        PayrollLineItem.objects.create(
            payroll_record=record,
            component_code="TDS",
            component_name="TDS",
            component_type="DEDUCTION",
            amount=preserved_tds,
            calculation_details={"source": "manual"},
        )

    if preserved_other and preserved_other > ZERO:
        PayrollLineItem.objects.create(
            payroll_record=record,
            component_code="OTHER_DEDUCTION",
            component_name="Other Deductions",
            component_type="DEDUCTION",
            amount=preserved_other,
            calculation_details={"source": "manual"},
        )

    _recompute_record_totals_from_line_items(record)

    _roll_up_totals(record.payroll_run)

    audit_log(
        user=recomputed_by,
        action="UPDATE",
        module="payroll",
        object_type="PayrollRecord",
        object_id=record.id,
        description=(
            f"Payroll record recomputed for "
            f"{record.employee.employee_code}."
        ),
    )

    return record


# =========================================================
# MANUAL DEDUCTION UPDATES
# =========================================================

@transaction.atomic
def update_payroll_record_deductions(
    record,
    tds=None,
    other_deductions=None,
    review_notes=None,
    updated_by=None,
):
    """
    Manually set TDS and/or other_deductions on a record.

    Only allowed while the parent run is DRAFT or GENERATED
    (not FINALIZED, and not after any payments exist).

    Replaces the TDS / OTHER_DEDUCTION line items and rebuilds totals.
    """
    if record.payroll_run.status == "FINALIZED":
        raise ValueError(
            "Cannot change deductions on a finalized payroll run."
        )

    if record.generation_status != "GENERATED":
        raise ValueError(
            "Only GENERATED records can be updated."
        )

    if record.payments.exists():
        raise ValueError(
            "Cannot change deductions after a payment has been recorded."
        )

    changed_fields = ["updated_at"]

    if tds is not None:
        tds_value = q2(Decimal(str(tds)))
        if tds_value < ZERO:
            raise ValueError("TDS cannot be negative.")
        record.tds = tds_value
        changed_fields.append("tds")

        record.line_items.filter(component_code="TDS").delete()
        if tds_value > ZERO:
            PayrollLineItem.objects.create(
                payroll_record=record,
                component_code="TDS",
                component_name="TDS",
                component_type="DEDUCTION",
                amount=tds_value,
                calculation_details={"source": "manual"},
            )

    if other_deductions is not None:
        od_value = q2(Decimal(str(other_deductions)))
        if od_value < ZERO:
            raise ValueError("Other deductions cannot be negative.")
        record.other_deductions = od_value
        changed_fields.append("other_deductions")

        record.line_items.filter(component_code="OTHER_DEDUCTION").delete()
        if od_value > ZERO:
            PayrollLineItem.objects.create(
                payroll_record=record,
                component_code="OTHER_DEDUCTION",
                component_name="Other Deductions",
                component_type="DEDUCTION",
                amount=od_value,
                calculation_details={"source": "manual"},
            )

    if review_notes is not None:
        record.review_notes = review_notes
        changed_fields.append("review_notes")
        # Acknowledging with review_notes also clears the review flag so
        # the admin can finalize after accepting the record as-is.
        if record.requires_review and review_notes.strip():
            record.requires_review = False
            changed_fields.append("requires_review")

    record.save(update_fields=changed_fields)

    _recompute_record_totals_from_line_items(record)

    _roll_up_totals(record.payroll_run)

    audit_log(
        user=updated_by,
        action="UPDATE",
        module="payroll",
        object_type="PayrollRecord",
        object_id=record.id,
        description="Manual deductions updated.",
    )

    return record


# =========================================================
# BULK ASSIGNMENT
# =========================================================

@transaction.atomic
def bulk_assign_salary(
    organization,
    employee_ids,
    salary_structure_id,
    effective_from,
    effective_to=None,
    reason=None,
    assigned_by=None,
):
    """
    Assign one salary structure to multiple employees, effective-dated.

    Validates:
      - employees belong to organization
      - employees are payroll-eligible
      - structure belongs to organization and is active
      - no overlapping assignment for each employee

    All validation happens BEFORE any writes.
    """
    employee_ids = list(employee_ids)
    if not employee_ids:
        raise ValueError("Select at least one employee.")
    if len(employee_ids) != len(set(employee_ids)):
        raise ValueError("employee_ids contains duplicate IDs.")

    if effective_to is not None and effective_to < effective_from:
        raise ValueError("effective_to cannot be before effective_from.")

    employees = list(
        Employee.objects.select_for_update()
        .filter(id__in=employee_ids, organization=organization)
        .order_by("id")
    )

    if len(employees) != len(set(employee_ids)):
        raise ValueError(
            "One or more employees do not belong to this organization."
        )

    for employee in employees:
        if (
            not employee.is_active
            or employee.employment_status not in PAYROLL_ELIGIBLE_STATUSES
        ):
            raise ValueError(
                f"Employee {employee.employee_code} is not payroll-eligible."
            )

    structure = SalaryStructure.objects.filter(
        id=salary_structure_id,
        organization=organization,
        is_active=True,
    ).first()

    if structure is None:
        raise ValueError(
            "Active salary structure not found in this organization."
        )

    for employee in employees:
        overlapping = EmployeeSalaryAssignment.objects.filter(
            organization=organization,
            employee=employee,
            effective_from__lte=effective_to or date_type.max,
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from)
        )

        conflict = overlapping.select_related("salary_structure").first()
        if conflict:
            raise ValueError(
                f"Employee {employee.employee_code} already has salary "
                f"assignment '{conflict.salary_structure.name}' from "
                f"{conflict.effective_from} to "
                f"{conflict.effective_to or 'open-ended'}. "
                f"Assignment date ranges cannot overlap."
            )

    assignments = [
        EmployeeSalaryAssignment(
            organization=organization,
            employee=employee,
            salary_structure=structure,
            effective_from=effective_from,
            effective_to=effective_to,
            reason=reason or None,
            assigned_by=assigned_by,
        )
        for employee in employees
    ]

    created = EmployeeSalaryAssignment.objects.bulk_create(assignments)

    audit_log(
        user=assigned_by,
        action="CREATE",
        module="payroll",
        object_type="EmployeeSalaryAssignment",
        object_id=None,
        description=(
            f"Bulk salary assignment: structure '{structure.name}' to "
            f"{len(created)} employee(s)."
        ),
    )

    return created


@transaction.atomic
def bulk_close_salary_assignments(
    organization,
    assignment_ids,
    effective_to,
    closed_by=None,
):
    """
    Close multiple open-ended salary assignments as of effective_to.

    Validates overlap of the resulting range against other assignments
    for the same employee. All validation happens BEFORE any writes.
    """
    assignment_ids = list(assignment_ids)
    if not assignment_ids:
        raise ValueError("assignment_ids must be a non-empty list.")
    if len(assignment_ids) != len(set(assignment_ids)):
        raise ValueError("assignment_ids contains duplicate IDs.")

    assignments = list(
        EmployeeSalaryAssignment.objects.select_for_update()
        .filter(id__in=assignment_ids, organization=organization)
        .select_related("employee", "salary_structure")
        .order_by("id")
    )

    if len(assignments) != len(set(assignment_ids)):
        raise ValueError(
            "One or more assignment IDs were not found in this organization."
        )

    for assignment in assignments:
        if effective_to < assignment.effective_from:
            raise ValueError(
                f"effective_to cannot be before effective_from for "
                f"assignment {assignment.id}."
            )

        if (
            assignment.effective_to is not None
            and effective_to > assignment.effective_to
        ):
            raise ValueError(
                f"Assignment {assignment.id} already ends on "
                f"{assignment.effective_to}; cannot extend it here."
            )

        if assignment.effective_to is None:
            other_conflict = (
                EmployeeSalaryAssignment.objects.filter(
                    organization=organization,
                    employee=assignment.employee,
                    effective_from__lte=effective_to,
                ).filter(
                    Q(effective_to__isnull=True)
                    | Q(effective_to__gte=assignment.effective_from)
                ).exclude(id=assignment.id).first()
            )
            if other_conflict:
                raise ValueError(
                    f"Cannot close assignment {assignment.id} to "
                    f"{effective_to}: it would overlap assignment "
                    f"{other_conflict.id}."
                )

    for assignment in assignments:
        assignment.effective_to = effective_to
        assignment.save(update_fields=["effective_to", "updated_at"])

    audit_log(
        user=closed_by,
        action="UPDATE",
        module="payroll",
        object_type="EmployeeSalaryAssignment",
        object_id=None,
        description=(
            f"Bulk salary close: {len(assignments)} assignment(s) "
            f"closed as of {effective_to}."
        ),
    )

    return assignments
