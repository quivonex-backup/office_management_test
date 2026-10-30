from django.db import models
from django.conf import settings
from django.db.models import Q, F
from django.core.validators import MinValueValidator


# =========================================================
# LEAVE TYPE
# =========================================================

class LeaveType(models.Model):

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="leave_types")

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True)

    annual_allocation = models.DecimalField(max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(0)])

    is_paid = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leave_types"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="unique_leave_type_name_per_org"),
            models.UniqueConstraint(fields=["organization", "code"], name="unique_leave_type_code_per_org"),
        ]

    def __str__(self):
        return f"{self.name} - {self.organization}"


# =========================================================
# EMPLOYEE LEAVE BALANCE
# =========================================================

class EmployeeLeaveBalance(models.Model):

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="leave_balances")
    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="leave_balances")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name="balances")

    # Calendar year (January to December)
    leave_year = models.PositiveSmallIntegerField()

    opening_balance = models.DecimalField(max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    allocated_days = models.DecimalField(max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    used_days = models.DecimalField(max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    pending_days = models.DecimalField(max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(0)])

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def available(self):
        return self.opening_balance + self.allocated_days - self.used_days - self.pending_days

    class Meta:
        db_table = "employee_leave_balances"
        ordering = ["-leave_year", "employee"]
        constraints = [
            models.UniqueConstraint(fields=["employee", "leave_type", "leave_year"], name="unique_employee_leave_balance_per_year"),
            models.CheckConstraint(condition=Q(opening_balance__gte=0), name="leave_balance_opening_non_negative"),
            models.CheckConstraint(condition=Q(allocated_days__gte=0), name="leave_balance_allocated_non_negative"),
            models.CheckConstraint(condition=Q(used_days__gte=0), name="leave_balance_used_non_negative"),
            models.CheckConstraint(condition=Q(pending_days__gte=0), name="leave_balance_pending_non_negative"),
        ]

    def __str__(self):
        return f"{self.employee.employee_code} - {self.leave_type.name} - {self.leave_year}"


# =========================================================
# LEAVE APPLICATION
# =========================================================

class LeaveApplication(models.Model):

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("CANCELLED", "Cancelled"),
    ]

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="leave_applications")
    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="leave_applications")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name="applications")

    start_date = models.DateField()
    end_date = models.DateField()

    # Calculated by backend using Calendar rules
    total_days = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0)])

    reason = models.TextField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING", db_index=True)

    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="leave_applications_reviewed")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leave_applications"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(end_date__gte=F("start_date")), name="valid_leave_application_date_range"),
            models.CheckConstraint(condition=Q(total_days__gt=0), name="leave_application_days_positive"),
        ]
        indexes = [
            models.Index(fields=["organization", "status", "start_date"], name="leave_org_status_start_idx"),
            models.Index(fields=["employee", "status"], name="leave_employee_status_idx"),
        ]

    def __str__(self):
        return f"{self.employee.employee_code} - {self.start_date} to {self.end_date} - {self.status}"


# =========================================================
# LEAVE BALANCE TRANSACTION
# =========================================================

class LeaveBalanceTransaction(models.Model):

    TRANSACTION_TYPE_CHOICES = [
        ("ALLOCATION", "Allocation"),
        ("PENDING_RESERVE", "Pending Reserve"),
        ("APPROVAL", "Approval"),
        ("REJECTION", "Rejection"),
        ("CANCELLATION", "Cancellation"),
        ("ADJUSTMENT", "Adjustment"),
    ]

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="leave_transactions")
    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="leave_transactions")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name="transactions")
    leave_balance = models.ForeignKey(EmployeeLeaveBalance, on_delete=models.PROTECT, related_name="transactions")
    leave_application = models.ForeignKey(LeaveApplication, on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions")

    transaction_type = models.CharField(max_length=25, choices=TRANSACTION_TYPE_CHOICES)

    # Signed value for audit history
    days = models.DecimalField(max_digits=6, decimal_places=2)

    remarks = models.TextField(blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="leave_transactions_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "leave_balance_transactions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "employee", "created_at"], name="leave_txn_org_emp_date_idx"),
            models.Index(fields=["leave_balance", "transaction_type"], name="leave_txn_balance_type_idx"),
        ]

    def __str__(self):
        return f"{self.employee.employee_code} - {self.transaction_type} - {self.days} days"
