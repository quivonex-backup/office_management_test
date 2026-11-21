from rest_framework import serializers

from .models import (
    DeviceToken,
    Notification,
    Announcement,
    AnnouncementAttachment,
    ProjectChatSettings,
    ProjectMessage,
    ProjectMessageAttachment,
)


# =========================================================
# SHARED HELPERS
# =========================================================
def _user_display_name(user):
    if not user:
        return None
    full_name = f"{user.first_name} {user.last_name}".strip()
    return full_name or user.username


def _user_sender_payload(user):
    if not user:
        return None

    employee = getattr(user, "employee_profile", None)

    role_label = None
    if employee and employee.designation:
        role_label = employee.designation
    elif user.role:
        role_label = user.role.name

    return {
        "id": user.id,
        "name": _user_display_name(user),
        "email": user.email,
        "profile_photo": (
            user.profile_photo.url if user.profile_photo else None
        ),
        "employee_code": employee.employee_code if employee else None,
        "role_label": role_label,
    }


# =========================================================
# FCM DEVICE TOKEN SERIALIZERS
# =========================================================
class DeviceTokenRegisterSerializer(serializers.Serializer):

    token = serializers.CharField(required=True, allow_blank=False, trim_whitespace=True)
    device_type = serializers.ChoiceField(choices=DeviceToken.DEVICE_CHOICES)

    def validate_token(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "FCM token cannot be blank."
            )

        return value


# =========================================================
# NOTIFICATION SERIALIZER
# =========================================================
class NotificationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Notification
        fields = [
            "id",
            "event_code",
            "title",
            "body",
            "reference_type",
            "reference_id",
            "priority",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields


# =========================================================
# ANNOUNCEMENT ATTACHMENT SERIALIZER
# =========================================================
class AnnouncementAttachmentSerializer(serializers.ModelSerializer):

    class Meta:
        model = AnnouncementAttachment
        fields = [
            "id",
            "title",
            "file",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
        ]


# =========================================================
# ANNOUNCEMENT (ADMIN READ) SERIALIZER
# =========================================================
class AnnouncementSerializer(serializers.ModelSerializer):

    attachments = AnnouncementAttachmentSerializer(many=True, read_only=True)
    created_by_details = serializers.SerializerMethodField()
    updated_by_details = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            "id",
            "organization",
            "title",
            "description",
            "priority",
            "is_pinned",
            "expires_at",
            "is_active",
            "attachments",
            "created_by_details",
            "updated_by_details",
            "created_at",
            "updated_at",
        ]

    def get_created_by_details(self, obj):
        if not obj.created_by:
            return None
        return {
            "id": obj.created_by.id,
            "name": _user_display_name(obj.created_by),
            "email": obj.created_by.email,
        }

    def get_updated_by_details(self, obj):
        if not obj.updated_by:
            return None
        return {
            "id": obj.updated_by.id,
            "name": _user_display_name(obj.updated_by),
            "email": obj.updated_by.email,
        }


# =========================================================
# ANNOUNCEMENT WRITE SERIALIZER
# =========================================================
class AnnouncementWriteSerializer(serializers.ModelSerializer):

    class Meta:
        model = Announcement
        fields = [
            "title",
            "description",
            "priority",
            "is_pinned",
            "expires_at",
        ]

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Title cannot be blank.")
        return value

    def validate_description(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Description cannot be blank.")
        return value


# =========================================================
# MY ANNOUNCEMENT (EMPLOYEE READ) SERIALIZER
# =========================================================
class MyAnnouncementSerializer(serializers.ModelSerializer):

    attachments = AnnouncementAttachmentSerializer(many=True, read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "description",
            "priority",
            "is_pinned",
            "expires_at",
            "attachments",
            "created_by_name",
            "created_at",
        ]

    def get_created_by_name(self, obj):
        return _user_display_name(obj.created_by)


# =========================================================
# PROJECT MESSAGE ATTACHMENT SERIALIZER
# =========================================================
class ProjectMessageAttachmentSerializer(serializers.ModelSerializer):

    class Meta:
        model = ProjectMessageAttachment
        fields = [
            "id",
            "title",
            "file",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
        ]


# =========================================================
# PROJECT MESSAGE SERIALIZER
# =========================================================
class ProjectMessageSerializer(serializers.ModelSerializer):

    attachments = ProjectMessageAttachmentSerializer(many=True, read_only=True)
    sender = serializers.SerializerMethodField()

    class Meta:
        model = ProjectMessage
        fields = [
            "id",
            "body",
            "sender",
            "attachments",
            "is_deleted",
            "created_at",
        ]

    def get_sender(self, obj):
        return _user_sender_payload(obj.sender)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.is_deleted:
            data["body"] = "[deleted]"
        return data


# =========================================================
# PROJECT MESSAGE SEND SERIALIZER
# =========================================================
class ProjectMessageSendSerializer(serializers.Serializer):

    project_id = serializers.IntegerField()
    body = serializers.CharField(max_length=2000)

    def validate_body(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Message body cannot be blank.")
        return value


# =========================================================
# PROJECT CHAT SETTINGS SERIALIZER
# =========================================================
class ProjectChatSettingsSerializer(serializers.ModelSerializer):

    project_id = serializers.IntegerField(source="project.id", read_only=True)
    project_name = serializers.CharField(
        source="project.project_name",
        read_only=True,
    )
    updated_by_details = serializers.SerializerMethodField()

    class Meta:
        model = ProjectChatSettings
        fields = [
            "project_id",
            "project_name",
            "posting_permission",
            "updated_by_details",
            "created_at",
            "updated_at",
        ]

    def get_updated_by_details(self, obj):
        if not obj.updated_by:
            return None
        return {
            "id": obj.updated_by.id,
            "name": _user_display_name(obj.updated_by),
            "email": obj.updated_by.email,
        }
    