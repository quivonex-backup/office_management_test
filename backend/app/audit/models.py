from django.db import models
from django.conf import settings


class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ("LOGIN", "Login"),
        ("LOGOUT", "Logout"),
        ("LOGIN_FAILED", "Login Failed"),
        ("CREATE", "Create"),
        ("UPDATE", "Update"),
        ("DELETE", "Delete"),
        ("VIEW", "View"),
        ("UPLOAD", "Upload"),
        ("DOWNLOAD", "Download"),
        ("PASSWORD_CHANGE", "Password Change"),
        ("OTP_SENT", "OTP Sent"),
        ("OTP_VERIFIED", "OTP Verified"),
        ("OTHER", "Other"),
    ]

    # User who performed the action
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )

    # Action type
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)

    # Module (e.g., USER, ROLE, CLIENT, PROJECT, PAYMENT, TASK)
    module = models.CharField(max_length=100, null=True, blank=True, db_index=True)

    # Object identification
    object_type = models.CharField(max_length=100, null=True, blank=True)
    object_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)

    # Description
    description = models.TextField(null=True, blank=True)

    # Data changes
    old_data = models.JSONField(null=True, blank=True)
    new_data = models.JSONField(null=True, blank=True)

    # Request metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    request_method = models.CharField(max_length=10, null=True, blank=True)
    request_path = models.TextField(null=True, blank=True)

    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["module", "action"]),
        ]

    def __str__(self):
        username = self.user.username if self.user else "Anonymous"
        return f"{username} - {self.action} - {self.module}"