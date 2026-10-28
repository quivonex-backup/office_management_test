from django.conf import settings
from django.db import models

# =========================================================
# EMPLOYEE MODEL
# =========================================================
class Employee(models.Model):

    # Employment status
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
        ("ON_LEAVE", "On Leave"),
        ("RESIGNED", "Resigned"),
        ("TERMINATED", "Terminated"),
    ]

    # Gender
    GENDER_CHOICES = [
        ("MALE", "Male"),
        ("FEMALE", "Female"),
        ("OTHER", "Other"),
    ]

    employee_code = models.CharField(max_length=20, unique=True, db_index=True)

    # ---- Personal Information ----
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True, null=True)

    # ---- Contact ----
    mobile = models.CharField(max_length=20, blank=True, null=True)
    alternate_mobile = models.CharField(max_length=20, blank=True, null=True)
    personal_email = models.EmailField(blank=True, null=True)

    # ---- Address ----
    address = models.TextField(blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    taluka = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)

    # ---- Employment ----
    designation = models.CharField(max_length=100, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    joining_date = models.DateField(blank=True, null=True)
    employment_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE", db_index=True)
    resignation_date = models.DateField(blank=True, null=True)

    # ---- Emergency Contact ----
    emergency_contact_name = models.CharField(max_length=150, blank=True, null=True)
    emergency_contact_number = models.CharField(max_length=20, blank=True, null=True)
    emergency_contact_relation = models.CharField(max_length=50, blank=True, null=True)

    # ---- Profile Photo ----
    profile_photo = models.FileField(upload_to="employees/profile/", blank=True, null=True)

    # ---- User ----
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="employee_profile")

    # ---- Organization ----
    organization = models.ForeignKey("accounts.Organization", on_delete=models.PROTECT, related_name="employees", db_index=True, null=True, blank=True)

    # ---- Audit ----
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="employees_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="employees_updated")

    # ---- Timestamps ----
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ---- Soft delete ----
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "employees"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee_code} - {self.first_name} {self.last_name}"


# =========================================================
# EMPLOYEE DOCUMENT MODEL
# =========================================================
class EmployeeDocument(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=200, blank=True, null=True)
    file = models.FileField(upload_to="employees/documents/", null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="employee_documents_uploaded"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "employee_documents"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee.employee_code} - {self.title or 'Document'}"