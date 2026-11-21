from django.conf import settings
from django.db import models



# =========================================================
# FCM MODEL
# =========================================================
class DeviceToken(models.Model):

    DEVICE_CHOICES = [
        ("ANDROID", "Android"),
        ("IOS", "iOS"),
        ("WEB", "Web"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="device_tokens")
    token = models.CharField(max_length=255, unique=True)
    device_type = models.CharField(max_length=20, choices=DEVICE_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "device_tokens"
        ordering = ["-id"]

    def __str__(self):
        return f"{self.user.username} - {self.device_type}"


# =========================================================
# NOTIFICATION MODEL
# =========================================================
class Notification(models.Model):

    PRIORITY_CHOICES = [
        ("NORMAL", "Normal"),
        ("HIGH", "High"),
    ]

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    event_code = models.CharField(max_length=60, db_index=True)
    title = models.CharField(max_length=255)
    body = models.TextField()
    reference_type = models.CharField(max_length=30, blank=True, null=True)
    reference_id = models.PositiveIntegerField(blank=True, null=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="NORMAL")
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"]),
        ]

    def __str__(self):
        return f"{self.recipient.username} - {self.event_code}"


# =========================================================
# ANNOUNCEMENT MODEL
# =========================================================
class Announcement(models.Model):

    PRIORITY_CHOICES = [
        ("NORMAL", "Normal"),
        ("HIGH", "High"),
        ("URGENT", "Urgent"),
    ]

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="announcements",
    )

    title = models.CharField(max_length=255)
    description = models.TextField()
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default="NORMAL",
    )

    is_pinned = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True, db_index=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcements_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcements_updated",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "announcements"
        ordering = ["-is_pinned", "-created_at"]
        indexes = [
            models.Index(fields=["organization", "is_active", "created_at"]),
            models.Index(fields=["organization", "is_pinned", "is_active"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.organization}"


# =========================================================
# ANNOUNCEMENT ATTACHMENT MODEL
# =========================================================
class AnnouncementAttachment(models.Model):

    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="announcements/attachments/")
    title = models.CharField(max_length=200, blank=True, null=True)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcement_attachments_uploaded",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "announcement_attachments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.announcement.title} - {self.title or 'Attachment'}"


# =========================================================
# PROJECT CHAT SETTINGS MODEL
# =========================================================
class ProjectChatSettings(models.Model):

    POSTING_PERMISSION_CHOICES = [
        ("ADMIN_ONLY", "Admin only"),
        ("ADMIN_AND_HEAD", "Admin and project head"),
        ("ALL_MEMBERS", "All project members"),
    ]

    project = models.OneToOneField(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="chat_settings",
    )
    posting_permission = models.CharField(
        max_length=20,
        choices=POSTING_PERMISSION_CHOICES,
        default="ALL_MEMBERS",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_chat_settings_updated",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "project_chat_settings"

    def __str__(self):
        return f"{self.project.project_name} - {self.posting_permission}"


# =========================================================
# PROJECT MESSAGE MODEL
# =========================================================
class ProjectMessage(models.Model):

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="chat_messages",
    )
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.PROTECT,
        related_name="project_chat_messages",
        db_index=True,
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_chat_messages_sent",
    )

    body = models.TextField()

    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_chat_messages_deleted",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "project_chat_messages"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["project", "is_deleted", "created_at"]),
            models.Index(fields=["project", "created_at"]),
        ]

    def __str__(self):
        return f"{self.project.project_name} - message #{self.pk}"


# =========================================================
# PROJECT MESSAGE ATTACHMENT MODEL
# =========================================================
class ProjectMessageAttachment(models.Model):

    message = models.ForeignKey(
        ProjectMessage,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="projects/chat/attachments/")
    title = models.CharField(max_length=200, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "project_chat_message_attachments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Message #{self.message_id} - {self.title or 'Attachment'}"
