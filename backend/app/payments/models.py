from django.conf import settings
from django.db import models

from app.projects.models import Project


# =========================================================
# PROJECT PAYMENT MODEL
# =========================================================

class ProjectPayment(models.Model):

    # Payment type
    PAYMENT_TYPE_CHOICES = [
        ("ADVANCE", "Advance"),
        ("INSTALLMENT", "Installment"),
    ]

    # Payment status
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PARTIALLY_PAID", "Partially Paid"),
        ("PAID", "Paid"),
        ("OVERDUE", "Overdue"),
        ("CANCELLED", "Cancelled"),
    ]

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="payments")
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, db_index=True)
    installment_number = models.PositiveIntegerField(null=True, blank=True)
    title = models.CharField(max_length=200, blank=True, null=True)

    # Expected amount for this payment/installment
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    # Total amount actually received
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Amount still remaining
    outstanding_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    due_date = models.DateField(null=True, blank=True)

    # Date the payment became fully paid
    # Actual transaction dates are stored in ProjectPaymentTransaction
    paid_date = models.DateField(null=True, blank=True)

    # Legacy / summary fields (kept for backward compatibility)
    payment_method = models.CharField(max_length=30, null=True, blank=True, editable=False)
    reference_number = models.CharField(max_length=100, null=True, blank=True, editable=False)

    notes = models.TextField(null=True, blank=True)

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="PENDING", db_index=True)

    organization = models.ForeignKey(
        "accounts.Organization", on_delete=models.PROTECT,
        related_name="project_payments", db_index=True, null=True, blank=True
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="project_payments_created"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="project_payments_updated"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "project_payments"
        ordering = ["payment_type", "installment_number", "-created_at"]

    def __str__(self):
        if self.payment_type == "ADVANCE":
            return f"{self.project.project_name} - Advance"
        return f"{self.project.project_name} - Installment {self.installment_number}"


# =========================================================
# PROJECT PAYMENT TRANSACTION MODEL
# =========================================================
#
# This represents the ACTUAL MONEY RECEIVED.
# Example:
#   ProjectPayment (Amount = 100000)
#     Transaction 1: UPI, Amount = 40000, UTR = ABC123
#     Transaction 2: Bank Transfer, Amount = 60000, UTR = XYZ789
#   Then: paid_amount = 100000, outstanding_amount = 0, status = PAID
# =========================================================

class ProjectPaymentTransaction(models.Model):

    PAYMENT_METHOD_CHOICES = [
        ("CASH", "Cash"),
        ("BANK_TRANSFER", "Bank Transfer"),
        ("UPI", "UPI"),
        ("CHEQUE", "Cheque"),
        ("CARD", "Card"),
        ("ONLINE", "Online"),
        ("OTHER", "Other"),
    ]

    STATUS_CHOICES = [
        ("SUCCESS", "Success"),
        ("PENDING", "Pending"),
        ("FAILED", "Failed"),
        ("CANCELLED", "Cancelled"),
        ("REFUNDED", "Refunded"),
    ]

    payment = models.ForeignKey(ProjectPayment, on_delete=models.PROTECT, related_name="transactions")
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES)
    transaction_date = models.DateField()
    reference_number = models.CharField(max_length=150, null=True, blank=True)
    utr_number = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    bank_name = models.CharField(max_length=150, null=True, blank=True)
    cheque_number = models.CharField(max_length=50, null=True, blank=True)
    cheque_date = models.DateField(null=True, blank=True)
    gateway_transaction_id = models.CharField(max_length=150, null=True, blank=True, db_index=True)
    gateway_order_id = models.CharField(max_length=150, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="SUCCESS", db_index=True)
    notes = models.TextField(null=True, blank=True)

    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="project_payment_transactions_received"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "project_payment_transactions"
        ordering = ["-transaction_date", "-created_at"]

    def __str__(self):
        return (
            f"{self.payment.project.project_name} - "
            f"{self.payment.payment_type} - "
            f"{self.amount} - {self.payment_method}"
        )


# =========================================================
# PROJECT PAYMENT DOCUMENT MODEL
# =========================================================

class ProjectPaymentDocument(models.Model):

    payment = models.ForeignKey(ProjectPayment, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=200, blank=True, null=True)
    file = models.FileField(upload_to="projects/payments/documents/", null=True, blank=True)
    description = models.TextField(blank=True, null=True)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="project_payment_documents_uploaded"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "project_payment_documents"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.payment.project.project_name} - {self.title or 'Payment Document'}"
