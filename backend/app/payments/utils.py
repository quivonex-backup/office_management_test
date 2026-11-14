from decimal import Decimal

from django.db import models
from django.utils import timezone

from .models import ProjectPaymentTransaction


# =========================================================
# RECALCULATE PROJECT PAYMENT
# =========================================================
#
# ONLY SUCCESS transactions count as received money.
#
# SUCCESS
#     -> counts
#
# PENDING
# FAILED
# CANCELLED
# REFUNDED
#     -> does NOT count
#
# This function is the SINGLE SOURCE OF TRUTH for:
#
#     paid_amount
#     outstanding_amount
#     status
#     paid_date
#
# =========================================================

def recalculate_project_payment(payment, updated_by=None):

    successful_amount = (
        ProjectPaymentTransaction.objects.filter(
            payment=payment,
            status="SUCCESS",
        )
        .aggregate(
            total=models.Sum("amount")
        )["total"]
        or Decimal("0")
    )

    # -----------------------------------------------------
    # PAID AMOUNT
    # -----------------------------------------------------

    payment.paid_amount = successful_amount

    # -----------------------------------------------------
    # FULLY PAID
    # -----------------------------------------------------

    if successful_amount >= payment.amount:

        payment.paid_amount = payment.amount
        payment.outstanding_amount = Decimal("0")
        payment.status = "PAID"

        latest_transaction = (
            ProjectPaymentTransaction.objects.filter(
                payment=payment,
                status="SUCCESS",
            )
            .order_by(
                "-transaction_date",
                "-created_at",
            )
            .first()
        )

        if latest_transaction:

            payment.paid_date = (
                latest_transaction.transaction_date
            )

        else:

            payment.paid_date = None

    # -----------------------------------------------------
    # PARTIALLY PAID
    # -----------------------------------------------------

    elif successful_amount > Decimal("0"):

        payment.paid_amount = successful_amount

        payment.outstanding_amount = (
            payment.amount -
            successful_amount
        )

        payment.paid_date = None

        if (
            payment.due_date
            and payment.due_date <
            timezone.now().date()
        ):

            payment.status = "OVERDUE"

        else:

            payment.status = "PARTIALLY_PAID"

    # -----------------------------------------------------
    # NOT PAID
    # -----------------------------------------------------

    else:

        payment.paid_amount = Decimal("0")

        payment.outstanding_amount = (
            payment.amount
        )

        payment.paid_date = None

        if (
            payment.due_date
            and payment.due_date <
            timezone.now().date()
        ):

            payment.status = "OVERDUE"

        else:

            payment.status = "PENDING"

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    payment.save(
        update_fields=[
            "paid_amount",
            "outstanding_amount",
            "status",
            "paid_date",
            "updated_at",
        ]
    )

    return payment