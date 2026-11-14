from django.conf import settings
from django.db import models
from app.clients.models import Client
from app.employees.models import Employee

# =========================================================
# PROJECT MODEL
# =========================================================
class Project(models.Model):
    project_code = models.CharField(max_length=20, unique=True, db_index=True)

    STATUS_CHOICES = [
        ("new", "New"),
        ("in_progress", "In Progress"),
        ("testing", "Testing"),
        ("completed", "Completed"),
        ("on_hold", "On Hold"),
        ("cancelled", "Cancelled"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]

    project_name = models.CharField(max_length=255)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="projects")
    project_type = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    deadline = models.DateField(blank=True, null=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    total_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    live_url = models.URLField(max_length=500, blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.PROTECT,
        related_name="projects",
        db_index=True,
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="projects_created"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="projects_updated"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "projects"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.project_code} - {self.project_name}"


# =========================================================
# PROJECT DOCUMENT MODEL
# =========================================================
class ProjectDocument(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=200, blank=True, null=True)
    file = models.FileField(upload_to="projects/documents/", null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="project_documents_uploaded")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "project_documents"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.project.project_name} - {self.title or 'Document'}"


# =========================================================
# PROJECT TEAM ALLOCATION MODEL
# =========================================================
class ProjectTeamAllocation(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="team_allocations")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="project_allocations")

    project_role = models.CharField(max_length=100, blank=True, null=True)
    allocation_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)

    allocated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="project_team_allocations_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "project_team_allocations"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project", "is_active"]),
            models.Index(fields=["employee", "is_active"]),
            models.Index(fields=["project", "employee"]),
        ]

    def __str__(self):
        return f"{self.project.project_name} - {self.employee.employee_code}"