from django.conf import settings
from django.db import models
from app.projects.models import Project
from app.vendors.models import Vendor


# =========================================================
# EXPENSE MODEL
# =========================================================
class Expense(models.Model):
    EXPENSE_TYPE_CHOICES = [
        ("food", "Food"),
        ("travel", "Travel"),
        ("utilities", "Utilities"),
        ("rent", "Rent"),
        ("software", "Software"),
        ("cloud", "Cloud"),
        ("equipment", "Equipment"),
        ("office", "Office"),
        ("maintenance", "Maintenance"),
        ("telephone", "Telephone"),
        ("marketing", "Marketing"),
        ("professional_services", "Professional Services"),
        ("other", "Other"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("paid", "Paid"),
        ("unpaid", "Unpaid")
    ]

    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("bank_transfer", "Bank Transfer"),
        ("upi", "UPI"),
        ("card", "Card"),
        ("cheque", "Cheque"),
        ("other", "Other"),
    ]

    expense_number = models.CharField(max_length=30, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    expense_type = models.CharField(max_length=50, choices=EXPENSE_TYPE_CHOICES, db_index=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    expense_date = models.DateField()
    due_date = models.DateField(blank=True, null=True)

    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="expenses", blank=True, null=True)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="expenses", blank=True, null=True)

    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="unpaid", db_index=True)
    payment_date = models.DateField(blank=True, null=True)
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True)
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True, db_index=True)

    organization = models.ForeignKey("accounts.Organization", on_delete=models.PROTECT, related_name="expenses", db_index=True, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses_updated")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "expenses"
        ordering = ["-expense_date", "-created_at"]

    def __str__(self):
        return f"{self.expense_number} - {self.title}"


# =========================================================
# EXPENSE DOCUMENT MODEL
# =========================================================
class ExpenseDocument(models.Model):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=200, blank=True, null=True)
    file = models.FileField(upload_to="expenses/documents/", null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="expense_documents_uploaded")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "expense_documents"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.expense.expense_number} - {self.title or 'Document'}"


# =========================================================
# RECURRING EXPENSE MODEL
# =========================================================
class RecurringExpense(models.Model):
    EXPENSE_TYPE_CHOICES = [
        ("electricity", "Electricity"),
        ("rent", "Office Rent"),
        ("cloud", "Cloud / AWS"),
        ("internet", "Internet"),
        ("software", "Software Subscription"),
        ("telephone", "Telephone"),
        ("other", "Other"),
    ]

    FREQUENCY_CHOICES = [
        ("monthly", "Monthly"), 
        ("quarterly", "Quarterly"),
        ("yearly", "Yearly")
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    expense_type = models.CharField(max_length=50, choices=EXPENSE_TYPE_CHOICES, db_index=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="recurring_expenses", blank=True, null=True)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="recurring_expenses", blank=True, null=True)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="monthly")
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    notes = models.TextField(blank=True, null=True)

    organization = models.ForeignKey("accounts.Organization", on_delete=models.PROTECT, related_name="recurring_expenses", db_index=True, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="recurring_expenses_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="recurring_expenses_updated")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "recurring_expenses"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


# =========================================================
# RECURRING EXPENSE ENTRY MODEL
# =========================================================
class RecurringExpenseEntry(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ("paid", "Paid"),
        ("unpaid", "Unpaid")
    ]

    PAYMENT_METHOD_CHOICES = [
        ("cash", "Cash"),
        ("bank_transfer", "Bank Transfer"),
        ("upi", "UPI"),
        ("card", "Card"),
        ("cheque", "Cheque"),
        ("other", "Other"),
    ]

    recurring_expense = models.ForeignKey(RecurringExpense, on_delete=models.CASCADE, related_name="entries")
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    due_date = models.DateField(blank=True, null=True)

    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="unpaid", db_index=True)
    payment_date = models.DateField(blank=True, null=True)
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True)
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="recurring_expense_entries_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="recurring_expense_entries_updated")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "recurring_expense_entries"
        ordering = ["-year", "-month", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["recurring_expense", "year", "month"], name="unique_recurring_expense_month")
        ]

    def __str__(self):
        return f"{self.recurring_expense.title} - {self.month}/{self.year}"


# =========================================================
# RECURRING EXPENSE ENTRY DOCUMENT MODEL
# =========================================================
class RecurringExpenseEntryDocument(models.Model):
    recurring_expense_entry = models.ForeignKey(RecurringExpenseEntry, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=200, blank=True, null=True)
    file = models.FileField(upload_to="expenses/recurring_entries/documents/", null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="recurring_expense_entry_documents_uploaded")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "recurring_expense_entry_documents"
        ordering = ["-created_at"]

    def __str__(self):
        re = self.recurring_expense_entry
        return f"{re.recurring_expense.title} - {re.month}/{re.year} - {self.title or 'Document'}"