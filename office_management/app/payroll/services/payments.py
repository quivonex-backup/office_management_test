"""
Payment recording and status maintenance.

Imports common only. No cycle back to processing/computation.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from ..models import (
    PayrollPayment,
)
from .common import (
    ZERO,
    q2,
    audit_log,
)


# =========================================================
# PAYMENT STATUS
# =========================================================

def update_payment_status(record):
    """
    Recompute paid_amount and payment_status from PayrollPayment rows.
    Does not touch any other field.
    """
    total_paid = (
        record.payments.aggregate(total=Sum("amount")).get("total") or ZERO
    )
    total_paid = q2(total_paid)

    record.paid_amount = total_paid

    if total_paid <= ZERO:
        record.payment_status = "UNPAID"
    elif total_paid < record.net:
        record.payment_status = "PARTIALLY_PAID"
    else:
        record.payment_status = "PAID"

    record.save(
        update_fields=["paid_amount", "payment_status", "updated_at"]
    )
    return record


# =========================================================
# RECORD PAYMENT
# =========================================================

@transaction.atomic
def record_payment(
    payroll_record,
    amount,
    payment_date,
    payment_mode="BANK_TRANSFER",
    transaction_reference=None,
    notes=None,
    recorded_by=None,
):
    """
    Record a payment against a FINALIZED payroll record.

    Validates:
      - parent run is FINALIZED
      - record generation_status is GENERATED
      - record has bank details for BANK_TRANSFER / UPI / CHEQUE
      - amount > 0 and does not exceed remaining balance
    """
    from ..models import PayrollRecord

    locked = PayrollRecord.objects.select_for_update().get(
        pk=payroll_record.pk,
    )
    payroll_record = locked

    if payroll_record.payroll_run.status != "FINALIZED":
        raise ValueError(
            "Payments can only be recorded against FINALIZED payroll runs."
        )

    if payroll_record.generation_status != "GENERATED":
        raise ValueError(
            "Cannot record a payment for a non-generated record."
        )

    if payment_mode in {"BANK_TRANSFER", "UPI", "CHEQUE"}:
        employee = payroll_record.employee
        if not employee.bank_account_number or not employee.bank_ifsc:
            raise ValueError(
                f"Employee {employee.employee_code}: bank details "
                f"(account number and IFSC) are required for "
                f"'{payment_mode}' payments."
            )

    amount = q2(Decimal(str(amount)))
    if amount <= ZERO:
        raise ValueError("Payment amount must be greater than zero.")

    already_paid = q2(
        payroll_record.payments.aggregate(total=Sum("amount")).get("total")
        or ZERO
    )
    remaining = q2(payroll_record.net - already_paid)

    if amount > remaining:
        raise ValueError(
            f"Payment amount {amount} exceeds the remaining "
            f"balance {remaining} for this record."
        )

    payment = PayrollPayment.objects.create(
        organization=payroll_record.organization,
        payroll_record=payroll_record,
        amount=amount,
        payment_date=payment_date,
        payment_mode=payment_mode,
        transaction_reference=transaction_reference or None,
        notes=notes or None,
        recorded_by=recorded_by,
    )

    update_payment_status(payroll_record)

    audit_log(
        user=recorded_by,
        action="CREATE",
        module="payroll",
        object_type="PayrollPayment",
        object_id=payment.id,
        description=(
            f"Payment of {amount} recorded for "
            f"employee {payroll_record.employee.employee_code}."
        ),
    )

    return payment


# =========================================================
# BULK PAYMENT
# =========================================================

@transaction.atomic
def bulk_record_payment_for_run(
    payroll_run,
    payment_date,
    payment_mode="BANK_TRANSFER",
    transaction_reference=None,
    notes=None,
    recorded_by=None,
    employee_ids=None,
):
    """
    Pay all unpaid GENERATED records of a FINALIZED run in full.
    Optionally restrict to employee_ids.

    Per-record errors are collected and returned; successful payments commit.
    """
    if payroll_run.status != "FINALIZED":
        raise ValueError(
            "Bulk payment is only allowed on FINALIZED payroll runs."
        )

    records_qs = payroll_run.records.filter(
        generation_status="GENERATED",
    ).exclude(payment_status="PAID")

    if employee_ids:
        records_qs = records_qs.filter(employee_id__in=employee_ids)

    records_qs = records_qs.select_related("employee").order_by("id")

    payments = []
    errors = []

    for record in records_qs.iterator():
        already_paid = q2(
            record.payments.aggregate(total=Sum("amount")).get("total")
            or ZERO
        )
        remaining = q2(record.net - already_paid)

        if remaining <= ZERO:
            continue

        try:
            payment = record_payment(
                payroll_record=record,
                amount=remaining,
                payment_date=payment_date,
                payment_mode=payment_mode,
                transaction_reference=transaction_reference,
                notes=notes,
                recorded_by=recorded_by,
            )
            payments.append(payment)
        except ValueError as exc:
            errors.append({
                "record_id": record.id,
                "employee_id": record.employee_id,
                "employee_code": record.employee.employee_code,
                "message": str(exc),
            })

    audit_log(
        user=recorded_by,
        action="BULK_PAYMENT",
        module="payroll",
        object_type="PayrollRun",
        object_id=payroll_run.id,
        description=(
            f"Bulk payment: {len(payments)} recorded, "
            f"{len(errors)} failed."
        ),
    )

    return {
        "payments_recorded": len(payments),
        "errors": errors,
        "payments": payments,
    }
