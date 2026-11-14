from django.conf import settings
from django.db import models


class SocialAccount(models.Model):
    PLATFORM_CHOICES = (
        ("FACEBOOK", "Facebook"),
        ("INSTAGRAM", "Instagram"),
    )

    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    account_name = models.CharField(max_length=255)
    account_id = models.CharField(max_length=255)
    access_token = models.TextField()
    token_expires_at = models.DateTimeField(null=True, blank=True)

    page_id = models.CharField(max_length=255, null=True, blank=True)
    instagram_user_id = models.CharField(max_length=255, null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="social_accounts",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "social_accounts"

    def __str__(self):
        return f"{self.platform} - {self.account_name}"


class SocialPost(models.Model):
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("SCHEDULED", "Scheduled"),
        ("PUBLISHING", "Publishing"),
        ("PUBLISHED", "Published"),
        ("PARTIAL", "Partially Published"),
        ("FAILED", "Failed"),
    )

    caption = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT",
    )
    
    scheduled_at = models.DateTimeField(null=True, blank=True)
    celery_task_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="social_posts",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "social_posts"

    def __str__(self):
        return f"Post #{self.pk}"


class SocialPostMedia(models.Model):
    MEDIA_TYPE_CHOICES = (
        ("IMAGE", "Image"),
        ("VIDEO", "Video"),
    )

    post = models.ForeignKey(
        SocialPost,
        on_delete=models.CASCADE,
        related_name="media",
    )
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPE_CHOICES)
    file = models.FileField(upload_to="social_media/posts/",null=True,blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "social_post_media"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.media_type} - Post #{self.post_id}"


class SocialPublication(models.Model):
    PLATFORM_CHOICES = (
        ("FACEBOOK", "Facebook"),
        ("INSTAGRAM", "Instagram"),
    )

    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("PUBLISHED", "Published"),
        ("FAILED", "Failed"),
    )

    post = models.ForeignKey(
        SocialPost,
        on_delete=models.CASCADE,
        related_name="publications",
    )
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )

    platform_post_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )
    platform_post_url = models.URLField(
        max_length=2000,
        null=True,
        blank=True,
    )
    error_message = models.TextField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "social_publications"

    def __str__(self):
        return f"{self.platform} - Post #{self.post_id} - {self.status}"