"""
Visitor log kept by the front desk. One row per visit; the same person
(name + mobile) can visit any number of times.

check_in_at defaults to the time the visit is added; check_out_at is
optional ("inside" = no check-out yet). Nothing is closed automatically.
"""
from django.conf import settings
from django.db import models


class Visit(models.Model):

    PURPOSE_CHOICES = [
        ("MEETING", "Meeting"),
        ("INTERVIEW", "Interview"),
        ("CLIENT", "Client visit"),
        ("VENDOR", "Vendor"),
        ("DELIVERY", "Delivery"),
        ("PERSONAL", "Personal"),
        ("OTHER", "Other"),
    ]
    ID_PROOF_CHOICES = [
        ("AADHAAR", "Aadhaar"),
        ("PAN", "PAN"),
        ("DL", "Driving licence"),
        ("PASSPORT", "Passport"),
        ("VOTER_ID", "Voter ID"),
        ("OTHER", "Other"),
    ]

    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="visits")
    visit_code = models.CharField(max_length=30, unique=True, db_index=True)
    branch = models.ForeignKey("accounts.Branch", on_delete=models.SET_NULL, null=True, blank=True, related_name="visits")

    visitor_name = models.CharField(max_length=150)
    visitor_mobile = models.CharField(max_length=20, db_index=True)
    visitor_email = models.EmailField(blank=True, null=True)
    visitor_company = models.CharField(max_length=150, blank=True, null=True)
    visitor_count = models.PositiveSmallIntegerField(default=1)

    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    purpose_note = models.CharField(max_length=255, blank=True, null=True)
    host = models.ForeignKey("employees.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="visits_hosted")

    check_in_at = models.DateTimeField(null=True, blank=True, db_index=True)
    check_out_at = models.DateTimeField(null=True, blank=True)

    # Only the type and the last 4 characters of the ID are kept.
    id_proof_type = models.CharField(max_length=20, choices=ID_PROOF_CHOICES, blank=True, null=True)
    id_proof_last4 = models.CharField(max_length=4, blank=True, null=True)
    photo = models.FileField(upload_to="visitors/photos/", null=True, blank=True)
    badge_number = models.CharField(max_length=30, blank=True, null=True)
    vehicle_number = models.CharField(max_length=20, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "visits"
        ordering = ["-check_in_at", "-created_at"]

    def __str__(self):
        return f"{self.visit_code} - {self.visitor_name}"
