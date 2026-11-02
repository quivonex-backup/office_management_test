from decimal import Decimal

from django.conf import settings
from django.db import models


ZERO = Decimal("0.00")


# =========================================================
# PAYROLL SETTINGS
# =========================================================

class PayrollSettings(models.Model):

    SALARY_BASIS_CHOICES = [
        ("CALENDAR_DAYS", "Calendar days in period"),
        ("FIXED_30", "Fixed 30 days"),
        ("WORKING_DAYS", "Working days in period"),
    ]

    MISSING_ATTENDANCE_CHOICES = [
        ("REVIEW", "Hold for review (no deduction)"),
        ("ABSENT", "Treat as absent (deduct)"),
        ("SKIP", "Skip (no deduction)"),
    ]

    PAYSLIP_MODE_CHOICES = [
        ("SIMPLE", "Simple (gross, deductions, net only)"),
        ("FULL", "Full (components + statutory breakdown)"),
    ]

    organization = models.OneToOneField("accounts.Organization", on_delete=models.CASCADE, related_name="payroll_settings")

    # Cycle
    cycle_start_day = models.PositiveSmallIntegerField(default=1)
    default_pay_day = models.PositiveSmallIntegerField(default=15)
    currency = models.CharField(max_length=3, default="INR")

    # Salary basis (per-day rate formula)
    salary_basis = models.CharField(max_length=20, choices=SALARY_BASIS_CHOICES, default="CALENDAR_DAYS")

    # Deduction multipliers
    absent_deduction_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.00"))
    half_day_deduction_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("0.50"))
    unpaid_leave_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.00"))

    # Overtime
    overtime_enabled = models.BooleanField(default=True)
    overtime_rate_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.50"))
    standard_work_hours_per_day = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("8.00"))

    # Missing attendance policy
    missing_attendance_action = models.CharField(max_length=20, choices=MISSING_ATTENDANCE_CHOICES, default="ABSENT")

    # Payslip detail level
    payslip_mode = models.CharField(
        max_length=10,
        choices=PAYSLIP_MODE_CHOICES,
        default="FULL",
        help_text=(
            "SIMPLE: payslip shows gross, total deductions, net only. "
            "Statutory still computed internally but not itemized. "
            "FULL: full component + statutory breakdown on payslip."
        ),
    )

    payroll_enabled = models.BooleanField(default=True)

    # Audit
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="payroll_settings_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="payroll_settings_updated")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payroll_settings"

    def __str__(self):
        return f"Payroll Settings - {self.organization}"


# =========================================================
# COMPANY STATUTORY SETTINGS
# =========================================================

class CompanyStatutorySettings(models.Model):

    PF_CONTRIBUTION_TYPE_CHOICES = [
        ("STATUTORY", "Statutory 12%"),
        ("VPF", "Voluntary PF"),
        ("COMPANY_SPECIFIC", "Company specific"),
    ]

    organization = models.OneToOneField("accounts.Organization", on_delete=models.CASCADE, related_name="statutory_settings")

    # PF
    is_pf_applicable = models.BooleanField(default=False)
    pf_establishment_code = models.CharField(max_length=50, blank=True, null=True)
    pf_org_name = models.CharField(max_length=200, blank=True, null=True)
    pf_contribution_type = models.CharField(max_length=20, choices=PF_CONTRIBUTION_TYPE_CHOICES, default="STATUTORY")

    # ESI
    is_esi_applicable = models.BooleanField(default=False)
    esi_employer_code = models.CharField(max_length=50, blank=True, null=True)
    esi_org_name = models.CharField(max_length=200, blank=True, null=True)

    # PT — org default state (used as fallback if employee.work_state is null)
    is_pt_applicable = models.BooleanField(default=False)
    pt_state = models.ForeignKey("location_master.StateMaster", on_delete=models.SET_NULL, null=True, blank=True, related_name="orgs_with_pt")
    pt_registration_number = models.CharField(max_length=50, blank=True, null=True)

    # TDS
    is_tds_applicable = models.BooleanField(default=False)
    tan_number = models.CharField(max_length=20, blank=True, null=True)
    tds_deductor_name = models.CharField(max_length=200, blank=True, null=True)
    tds_deductor_address = models.TextField(blank=True, null=True)

    # LWF
    is_lwf_applicable = models.BooleanField(default=False)
    lwf_state = models.ForeignKey("location_master.StateMaster", on_delete=models.SET_NULL, null=True, blank=True, related_name="orgs_with_lwf")
    lwf_registration_number = models.CharField(max_length=50, blank=True, null=True)

    # Audit
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="statutory_settings_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="statutory_settings_updated")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "company_statutory_settings"

    def __str__(self):
        return f"Statutory Settings - {self.organization}"


# =========================================================
# SALARY COMPONENT
# Global (super admin) or org-specific reusable earning /
# deduction definitions.
# =========================================================

class SalaryComponent(models.Model):

    COMPONENT_TYPE_CHOICES = [
        ("EARNING", "Earning"),
        ("DEDUCTION", "Deduction"),
    ]

    CALCULATION_TYPE_CHOICES = [
        ("FIXED", "Fixed amount"),
        ("PERCENTAGE", "Percentage of another component"),
    ]

    COMPONENT_ROLE_CHOICES = [
        ("BASIC", "Basic"),
        ("DA", "Dearness Allowance"),
        ("HRA", "House Rent Allowance"),
        ("ALLOWANCE", "Allowance"),
        ("BONUS", "Bonus"),
        ("OT", "Overtime"),
        ("PF_EMPLOYEE", "PF - Employee"),
        ("PF_EMPLOYER", "PF - Employer"),
        ("ESI_EMPLOYEE", "ESI - Employee"),
        ("ESI_EMPLOYER", "ESI - Employer"),
        ("PT", "Professional Tax"),
        ("TDS", "TDS"),
        ("LWF", "Labour Welfare Fund"),
        ("OTHER", "Other"),
    ]

    # NULL = global component (super admin). Non-NULL = org-specific.
    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, null=True, blank=True, related_name="salary_components")

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    description = models.TextField(blank=True, null=True)

    component_type = models.CharField(max_length=20, choices=COMPONENT_TYPE_CHOICES)
    calculation_type = models.CharField(max_length=20, choices=CALCULATION_TYPE_CHOICES, default="FIXED")
    component_role = models.CharField(max_length=20, choices=COMPONENT_ROLE_CHOICES, default="OTHER")

    percentage_of_component = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="percentage_dependents")

    is_taxable = models.BooleanField(default=True)
    is_pf_eligible = models.BooleanField(default=False)
    is_esi_eligible = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    # Audit
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="salary_components_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="salary_components_updated")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "salary_components"
        ordering = ["display_order", "name"]

    def __str__(self):
        org_tag = self.organization.organization_name if self.organization else "GLOBAL"
        return f"{self.name} ({self.code}) - {org_tag}"


# =========================================================
# SALARY STRUCTURE
# =========================================================

class SalaryStructure(models.Model):

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="salary_structures")

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    # Audit
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="salary_structures_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="salary_structures_updated")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "salary_structures"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code}) - {self.organization}"


# =========================================================
# SALARY STRUCTURE COMPONENT
# =========================================================

class SalaryStructureComponent(models.Model):

    salary_structure = models.ForeignKey(SalaryStructure, on_delete=models.CASCADE, related_name="components")
    salary_component = models.ForeignKey(SalaryComponent, on_delete=models.PROTECT, related_name="structure_entries")

    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    percentage = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "salary_structure_components"
        ordering = ["salary_component__display_order"]

    def __str__(self):
        return f"{self.salary_structure.name} - {self.salary_component.name}"


# =========================================================
# EMPLOYEE SALARY ASSIGNMENT
# =========================================================

class EmployeeSalaryAssignment(models.Model):

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="salary_assignments")
    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="salary_assignments")
    salary_structure = models.ForeignKey(SalaryStructure, on_delete=models.PROTECT, related_name="employee_assignments")

    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    reason = models.TextField(blank=True, null=True)

    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="salary_assignments_made")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "employee_salary_assignments"
        ordering = ["-effective_from"]
        indexes = [models.Index(fields=["organization", "employee", "effective_from"])]

    def __str__(self):
        return f"{self.employee} - {self.salary_structure.name} - {self.effective_from}"


# =========================================================
# STATUTORY RATE CONFIG
# Super-admin managed, versioned rates.
# NULL organization = federal default.
# =========================================================

class StatutoryRateConfig(models.Model):

    COMPONENT_CODE_CHOICES = [
        ("PF_EMPLOYEE", "PF - Employee"),
        ("PF_EMPLOYER", "PF - Employer"),
        ("EPS", "EPS Pension"),
        ("EDLI", "EDLI"),
        ("PF_ADMIN", "PF Admin Charges"),
        ("ESI_EMPLOYEE", "ESI - Employee"),
        ("ESI_EMPLOYER", "ESI - Employer"),
        ("PT", "Professional Tax"),
        ("TDS", "TDS"),
        ("LWF_EMPLOYEE", "LWF - Employee"),
        ("LWF_EMPLOYER", "LWF - Employer"),
    ]

    CALCULATION_BASE_CHOICES = [
        ("BASIC", "Basic"),
        ("BASIC_DA", "Basic + DA"),
        ("PF_ELIGIBLE", "Sum of PF-eligible earnings"),
        ("ESI_ELIGIBLE", "Sum of ESI-eligible earnings"),
        ("GROSS", "Gross earnings"),
    ]

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, null=True, blank=True, related_name="statutory_rate_configs")

    component_code = models.CharField(max_length=30, choices=COMPONENT_CODE_CHOICES)
    rate_percentage = models.DecimalField(max_digits=6, decimal_places=4)
    wage_ceiling = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    calculation_base = models.CharField(max_length=20, choices=CALCULATION_BASE_CHOICES)

    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    notification_reference = models.CharField(max_length=200, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    # Audit
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="statutory_rate_configs_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="statutory_rate_configs_updated")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "statutory_rate_configs"
        ordering = ["-effective_from", "component_code"]
        indexes = [models.Index(fields=["component_code", "effective_from"])]

    def __str__(self):
        return f"{self.component_code} = {self.rate_percentage}% (from {self.effective_from})"


# =========================================================
# STATUTORY SLAB
# Super-admin managed, versioned state slabs.
# =========================================================

class StatutorySlab(models.Model):

    SLAB_TYPE_CHOICES = [
        ("PT", "Professional Tax"),
        ("TDS_OLD_REGIME", "TDS - Old Regime"),
        ("TDS_NEW_REGIME", "TDS - New Regime"),
        ("LWF", "Labour Welfare Fund"),
    ]

    FREQUENCY_CHOICES = [
        ("MONTHLY", "Monthly"),
        ("HALF_YEARLY", "Half-Yearly"),
        ("ANNUAL", "Annual"),
    ]

    slab_type = models.CharField(max_length=20, choices=SLAB_TYPE_CHOICES)
    state = models.ForeignKey("location_master.StateMaster", on_delete=models.SET_NULL, null=True, blank=True, related_name="statutory_slabs")

    income_from = models.DecimalField(max_digits=12, decimal_places=2)
    income_to = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    fixed_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rate_percentage = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)

    is_february_override = models.BooleanField(default=False)
    additional_amount = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)

    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="MONTHLY")

    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    notes = models.TextField(blank=True, null=True)

    # Audit
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="statutory_slabs_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="statutory_slabs_updated")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "statutory_slabs"
        ordering = ["slab_type", "state", "income_from"]
        indexes = [models.Index(fields=["slab_type", "state", "income_from"])]

    def __str__(self):
        return f"{self.slab_type} - {self.state} - {self.income_from} to {self.income_to or '∞'}"


# =========================================================
# PAYROLL RUN
# =========================================================

class PayrollRun(models.Model):

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("GENERATED", "Generated"),
        ("FINALIZED", "Finalized"),
    ]

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="payroll_runs")

    period_start = models.DateField()
    period_end = models.DateField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")

    total_employees = models.PositiveIntegerField(default=0)
    total_gross = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    total_deductions = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    total_net = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)

    # Audit
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="payroll_runs_created")
    finalized_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="payroll_runs_finalized")
    finalized_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payroll_runs"
        ordering = ["-period_start"]
        indexes = [models.Index(fields=["organization", "period_start", "period_end"])]

    def __str__(self):
        return f"{self.organization} - {self.period_start} to {self.period_end} - {self.status}"


# =========================================================
# PAYROLL RECORD
# =========================================================

class PayrollRecord(models.Model):

    GENERATION_STATUS_CHOICES = [
        ("GENERATED", "Generated"),
        ("SKIPPED", "Skipped"),
        ("ERROR", "Error"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("UNPAID", "Unpaid"),
        ("PARTIALLY_PAID", "Partially Paid"),
        ("PAID", "Paid"),
    ]

    payroll_run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name="records")
    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="payroll_records")
    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="payroll_records")

    # ---- Attendance snapshot ----
    present_days = models.DecimalField(max_digits=6, decimal_places=2, default=ZERO)
    half_days = models.DecimalField(max_digits=6, decimal_places=2, default=ZERO)
    absent_days = models.DecimalField(max_digits=6, decimal_places=2, default=ZERO)
    paid_leave_days = models.DecimalField(max_digits=6, decimal_places=2, default=ZERO)
    unpaid_leave_days = models.DecimalField(max_digits=6, decimal_places=2, default=ZERO)
    holiday_days = models.DecimalField(max_digits=6, decimal_places=2, default=ZERO)
    weekly_off_days = models.DecimalField(max_digits=6, decimal_places=2, default=ZERO)
    overtime_hours = models.DecimalField(max_digits=8, decimal_places=2, default=ZERO)

    # ---- Salary snapshot ----
    monthly_salary = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    per_day_rate = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)

    # ---- Statutory snapshot ----
    pf_employee = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    pf_employer = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    eps = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    edli = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    esi_employee = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    esi_employer = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    pt = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    tds = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    lwf_employee = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    lwf_employer = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)

    # ---- Totals ----
    gross_earnings = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    total_deductions = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    net = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)

    # ---- Payment ----
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="UNPAID")
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)

    # ---- Generation state ----
    generation_status = models.CharField(max_length=20, choices=GENERATION_STATUS_CHOICES, default="GENERATED")
    generation_notes = models.TextField(blank=True, null=True)
    requires_review = models.BooleanField(default=False)
    review_notes = models.TextField(blank=True, null=True)

    # ---- Audit snapshot ----
    breakdown = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payroll_records"
        ordering = ["-payroll_run__period_start", "employee"]
        indexes = [
            models.Index(fields=["payroll_run", "employee"]),
            models.Index(fields=["organization", "employee"]),
            models.Index(fields=["payment_status"]),
            models.Index(fields=["generation_status"]),
        ]

    def __str__(self):
        return f"{self.employee} - {self.payroll_run} - Net: {self.net}"


# =========================================================
# PAYROLL LINE ITEM
# Per-component breakdown for payslip & compliance returns.
# =========================================================

class PayrollLineItem(models.Model):

    LINE_TYPE_CHOICES = [
        ("EARNING", "Earning"),
        ("DEDUCTION", "Deduction"),
        ("LOP", "Loss of Pay"),
    ]

    payroll_record = models.ForeignKey(PayrollRecord, on_delete=models.CASCADE, related_name="line_items")

    component_code = models.CharField(max_length=20)
    component_name = models.CharField(max_length=100)
    component_type = models.CharField(max_length=20, choices=LINE_TYPE_CHOICES)

    amount = models.DecimalField(max_digits=14, decimal_places=2)
    calculation_details = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payroll_line_items"
        ordering = ["payroll_record", "component_type", "-amount"]
        indexes = [models.Index(fields=["payroll_record", "component_type"])]

    def __str__(self):
        return f"Record {self.payroll_record_id} - {self.component_code} - {self.amount}"


# =========================================================
# PAYROLL PAYMENT
# =========================================================

class PayrollPayment(models.Model):

    PAYMENT_MODE_CHOICES = [
        ("BANK_TRANSFER", "Bank Transfer"),
        ("CASH", "Cash"),
        ("UPI", "UPI"),
        ("CHEQUE", "Cheque"),
    ]

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="payroll_payments")
    payroll_record = models.ForeignKey(PayrollRecord, on_delete=models.CASCADE, related_name="payments")

    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_date = models.DateField()
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, default="BANK_TRANSFER")
    transaction_reference = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="payroll_payments_recorded")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payroll_payments"
        ordering = ["-payment_date", "-created_at"]
        indexes = [
            models.Index(fields=["organization", "payment_date"]),
            models.Index(fields=["payroll_record"]),
        ]

    def __str__(self):
        return f"{self.payroll_record_id} - ₹{self.amount} on {self.payment_date}"
