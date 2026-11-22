"""
Recruitment: Applicant -> Verification -> Onboarding -> Employee.

The three stages are one workflow on one Applicant row:
  stage   APPLICANT | VERIFICATION | ONBOARDING | COMPLETED | CLOSED
  status  PENDING | SHORTLISTED | SELECTED | REJECTED | WITHDRAWN  (recruitment decision)
Checklists for VERIFICATION and ONBOARDING are ApplicantCheck rows.
Offers are immutable ApplicantOffer rows (a revision is a new version).
Rejected / withdrawn applicants stay applicants (stage CLOSED) and can never
be converted.
"""
from django.conf import settings
from django.db import models


class Applicant(models.Model):

    STAGE_CHOICES = [
        ("APPLICANT", "Applicant"),
        ("VERIFICATION", "Verification"),
        ("ONBOARDING", "Onboarding"),
        ("COMPLETED", "Completed"),
        ("CLOSED", "Closed"),
    ]
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("SHORTLISTED", "Shortlisted"),
        ("SELECTED", "Selected"),
        ("REJECTED", "Rejected"),
        ("WITHDRAWN", "Withdrawn"),
    ]
    SOURCE_CHOICES = [
        ("JOB_PORTAL", "Job portal"),
        ("REFERRAL", "Employee referral"),
        ("WEBSITE", "Company website"),
        ("WALK_IN", "Walk-in"),
        ("CAMPUS", "Campus"),
        ("AGENCY", "Agency"),
        ("SOCIAL", "Social media"),
        ("OTHER", "Other"),
    ]
    GENDER_CHOICES = [("MALE", "Male"), ("FEMALE", "Female"), ("OTHER", "Other")]

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="applicants")
    applicant_code = models.CharField(max_length=30, unique=True, db_index=True)

    # ---- Personal ----
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    mobile = models.CharField(max_length=20)
    alternate_mobile = models.CharField(max_length=20, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.ForeignKey("location_master.StateMaster", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    pincode = models.CharField(max_length=10, blank=True, null=True)

    # ---- Applied position ----
    designation = models.ForeignKey("employees.Designation", on_delete=models.SET_NULL, null=True, blank=True, related_name="applicants")
    position_title = models.CharField(max_length=150, blank=True, null=True)   # free text when no designation fits
    department = models.ForeignKey("employees.Department", on_delete=models.SET_NULL, null=True, blank=True, related_name="applicants")
    branch = models.ForeignKey("accounts.Branch", on_delete=models.SET_NULL, null=True, blank=True, related_name="applicants")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="OTHER")
    referred_by = models.ForeignKey("employees.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="referred_applicants")
    applied_on = models.DateField()

    # ---- Profile ----
    total_experience_years = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    current_company = models.CharField(max_length=150, blank=True, null=True)
    current_designation = models.CharField(max_length=150, blank=True, null=True)
    current_ctc = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    expected_ctc = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    notice_period_days = models.PositiveIntegerField(null=True, blank=True)
    skills = models.TextField(blank=True, null=True)
    # [{"degree", "institution", "year", "score"}]
    education = models.JSONField(default=list, blank=True)
    # [{"company", "designation", "from", "to", "ctc", "reason_for_leaving"}]
    experience = models.JSONField(default=list, blank=True)
    remarks = models.TextField(blank=True, null=True)

    # ---- Workflow ----
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default="APPLICANT", db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING", db_index=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_applicants")

    # ---- Onboarding details (become Employee fields on convert) ----
    joining_date = models.DateField(null=True, blank=True)
    reports_to = models.ForeignKey("employees.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    access_role = models.ForeignKey("accounts.AccessRole", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    # Extra employee fields: work_state_id, pan_number, pf_uan, esi_ip_number,
    # tax_regime, bank_*, upi_id, emergency_contact_* ...
    onboarding_data = models.JSONField(default=dict, blank=True)

    employee = models.OneToOneField("employees.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="source_applicant")
    converted_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="applicants_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="applicants_updated")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "applicants"
        ordering = ["-applied_on", "-created_at"]
        indexes = [
            models.Index(fields=["organization", "stage", "status"]),
            models.Index(fields=["organization", "email"]),
        ]

    def __str__(self):
        return f"{self.applicant_code} - {self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return " ".join(p for p in [self.first_name, self.middle_name, self.last_name] if p)


class ApplicantDocument(models.Model):
    TYPE_CHOICES = [
        ("RESUME", "Resume"),
        ("ID_PROOF", "Identity proof"),
        ("ADDRESS_PROOF", "Address proof"),
        ("EDUCATION", "Education"),
        ("EXPERIENCE", "Experience / relieving letter"),
        ("PAYSLIP", "Payslip"),
        ("PHOTO", "Photo"),
        ("OFFER_LETTER", "Signed offer letter"),
        ("OTHER", "Other"),
    ]

    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="OTHER")
    title = models.CharField(max_length=200, blank=True, null=True)
    file = models.FileField(upload_to="recruitment/documents/", null=True, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "applicant_documents"
        ordering = ["-created_at"]


class ApplicantInterview(models.Model):
    MODE_CHOICES = [("IN_PERSON", "In person"), ("PHONE", "Phone"), ("VIDEO", "Video")]
    RESULT_CHOICES = [
        ("SCHEDULED", "Scheduled"),
        ("PASSED", "Passed"),
        ("FAILED", "Failed"),
        ("ON_HOLD", "On hold"),
        ("NO_SHOW", "No show"),
        ("CANCELLED", "Cancelled"),
    ]

    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name="interviews")
    round_name = models.CharField(max_length=100)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="IN_PERSON")
    interviewer = models.ForeignKey("employees.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="applicant_interviews")
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, default="SCHEDULED")
    rating = models.PositiveSmallIntegerField(null=True, blank=True)   # 1-5
    feedback = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "applicant_interviews"
        ordering = ["scheduled_at", "id"]


class ApplicantStatusHistory(models.Model):
    """Append-only log of every workflow change."""

    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name="history")
    action = models.CharField(max_length=40)        # CREATED, STATUS_CHANGED, OFFER_CREATED, ...
    from_stage = models.CharField(max_length=20, blank=True, null=True)
    to_stage = models.CharField(max_length=20, blank=True, null=True)
    from_status = models.CharField(max_length=20, blank=True, null=True)
    to_status = models.CharField(max_length=20, blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "applicant_status_history"
        ordering = ["created_at", "id"]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Applicant history rows cannot be changed.")
        super().save(*args, **kwargs)


class ApplicantOffer(models.Model):
    """
    Offer terms never change after creation. Only the status moves:
    DRAFT -> SENT -> ACCEPTED | DECLINED ; DRAFT/SENT -> REVOKED ;
    any open offer -> SUPERSEDED when a new version is created.
    """

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SENT", "Sent"),
        ("ACCEPTED", "Accepted"),
        ("DECLINED", "Declined"),
        ("REVOKED", "Revoked"),
        ("SUPERSEDED", "Superseded"),
    ]
    TERM_FIELDS = (
        "designation_id", "department_id", "branch_id", "joining_date",
        "salary_structure_id", "annual_ctc", "monthly_gross", "breakup", "notes",
    )

    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name="offers")
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT", db_index=True)

    designation = models.ForeignKey("employees.Designation", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    department = models.ForeignKey("employees.Department", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    branch = models.ForeignKey("accounts.Branch", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    joining_date = models.DateField()
    salary_structure = models.ForeignKey("payroll.SalaryStructure", on_delete=models.PROTECT, related_name="+")
    annual_ctc = models.DecimalField(max_digits=14, decimal_places=2)
    monthly_gross = models.DecimalField(max_digits=12, decimal_places=2)
    breakup = models.JSONField(default=dict, blank=True)    # snapshot from the payroll calculator
    notes = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    status_changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        db_table = "applicant_offers"
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(fields=["applicant", "version"], name="unique_applicant_offer_version"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values(*self.TERM_FIELDS).first()
            if old:
                for field in self.TERM_FIELDS:
                    if old[field] != getattr(self, field):
                        raise ValueError("Offer terms cannot be changed. Create a revised offer instead.")
        super().save(*args, **kwargs)


class ApplicantCheck(models.Model):
    """One checklist line of the VERIFICATION or ONBOARDING stage."""

    STAGE_CHOICES = [("VERIFICATION", "Verification"), ("ONBOARDING", "Onboarding")]
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("DONE", "Done"),
        ("REJECTED", "Rejected"),
        ("WAIVED", "Waived"),
    ]

    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name="checks")
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES)
    key = models.CharField(max_length=40)
    label = models.CharField(max_length=150)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    is_system = models.BooleanField(default=False)      # set by the workflow, not by hand
    note = models.TextField(blank=True, null=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "applicant_checks"
        ordering = ["stage", "sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["applicant", "stage", "key"], name="unique_applicant_check"),
        ]
