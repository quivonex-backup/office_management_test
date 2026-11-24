"""
Company assets (laptops, phones, ID cards, SIMs ...) and who holds them.

  AssetCategory    per organization list (Laptop, Phone, ...)
  Asset            status AVAILABLE | ASSIGNED | IN_REPAIR | RETIRED | LOST;
                   current_holder is set only while ASSIGNED
  AssetAssignment  one row per issue -> return (history of holders)
"""
from django.conf import settings
from django.db import models


class AssetCategory(models.Model):
    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="asset_categories")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "asset_categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Asset(models.Model):

    STATUS_CHOICES = [
        ("AVAILABLE", "Available"),
        ("ASSIGNED", "Assigned"),
        ("IN_REPAIR", "In repair"),
        ("RETIRED", "Retired"),
        ("LOST", "Lost"),
    ]

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="assets")
    asset_code = models.CharField(max_length=30, unique=True, db_index=True)
    category = models.ForeignKey(AssetCategory, on_delete=models.PROTECT, related_name="assets")
    name = models.CharField(max_length=150)
    brand = models.CharField(max_length=100, blank=True, null=True)
    model_number = models.CharField(max_length=100, blank=True, null=True)
    serial_number = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    branch = models.ForeignKey("accounts.Branch", on_delete=models.SET_NULL, null=True, blank=True, related_name="assets")

    purchase_date = models.DateField(blank=True, null=True)
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    warranty_until = models.DateField(blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="AVAILABLE", db_index=True)
    current_holder = models.ForeignKey(
        "employees.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="held_assets",
    )
    notes = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "assets"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.asset_code} - {self.name}"


class AssetAssignment(models.Model):

    CONDITION_CHOICES = [
        ("NEW", "New"),
        ("GOOD", "Good"),
        ("FAIR", "Fair"),
        ("DAMAGED", "Damaged"),
    ]

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="assignments")
    employee = models.ForeignKey("employees.Employee", on_delete=models.PROTECT, related_name="asset_assignments")
    assigned_on = models.DateField()
    condition_on_issue = models.CharField(max_length=10, choices=CONDITION_CHOICES, blank=True, null=True)
    issue_note = models.TextField(blank=True, null=True)
    returned_on = models.DateField(blank=True, null=True)
    condition_on_return = models.CharField(max_length=10, choices=CONDITION_CHOICES, blank=True, null=True)
    return_note = models.TextField(blank=True, null=True)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    returned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "asset_assignments"
        ordering = ["-assigned_on", "-id"]

    def __str__(self):
        return f"{self.asset.asset_code} -> {self.employee.employee_code}"
