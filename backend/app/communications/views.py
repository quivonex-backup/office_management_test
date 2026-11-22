from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from rest_framework import status
from rest_framework.parsers import (
    JSONParser,
    FormParser,
    MultiPartParser,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.services import (
    get_user_organization,
    get_project_permission,
)
from common.s3_utils import upload_to_s3, delete_from_s3
from app.audit.services import log_activity

from .models import (
    DeviceToken,
    Notification,
    Announcement,
    AnnouncementAttachment,
    ProjectChatSettings,
    ProjectMessage,
    ProjectMessageAttachment,
)
from .serializers import (
    DeviceTokenRegisterSerializer,
    NotificationSerializer,
    AnnouncementSerializer,
    AnnouncementWriteSerializer,
    MyAnnouncementSerializer,
    ProjectMessageSerializer,
    ProjectMessageSendSerializer,
    ProjectChatSettingsSerializer,
)
from .notification_service import notify


# =========================================================
# SHARED HELPERS
# =========================================================
def _can_manage_announcements(request, organization):
    """
    Same rule as the rest of the system: the organization owner, or an
    access role with announcement.manage. The super admin has no access
    inside an organization's data.
    """
    from common.permissions import has_perm

    return has_perm(request, organization, "announcement.manage")


def _active_announcements_qs(organization):
    now = timezone.now()
    return (
        Announcement.objects
        .filter(organization=organization, is_active=True)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now))
    )


def _can_post_to_chat(permission, project, user):
    """
    Return (allowed: bool, reason: str | None).
    permission: 'ADMIN' | 'HEAD' | 'MEMBER'
    """
    if permission == "ADMIN":
        return True, None

    settings_obj, _ = ProjectChatSettings.objects.get_or_create(
        project=project,
    )
    posting_permission = settings_obj.posting_permission

    if posting_permission == "ADMIN_ONLY":
        return False, "Only the admin can post in this project's chat."

    if posting_permission == "ADMIN_AND_HEAD":
        if permission == "HEAD":
            return True, None
        return (
            False,
            "Only the admin and project head can post in this project's chat.",
        )

    # ALL_MEMBERS
    return True, None


def _can_current_user_post(permission, project):
    """
    Return boolean without a reason — used to pre-compute
    `can_current_user_post` in list responses.
    """
    if permission == "ADMIN":
        return True

    settings_obj, _ = ProjectChatSettings.objects.get_or_create(
        project=project,
    )
    posting_permission = settings_obj.posting_permission

    if posting_permission == "ADMIN_ONLY":
        return False
    if posting_permission == "ADMIN_AND_HEAD":
        return permission == "HEAD"
    return True


def _get_announcement_recipients(organization, exclude_user_id=None):
    """
    Returns all active Users in the organization, excluding the
    creator (no self-notification). Deduplicated by user id.
    """
    from app.accounts.models import OrganizationMembership

    memberships = (
        OrganizationMembership.objects
        .filter(
            organization=organization,
            is_active=True,
            user__is_active=True,
        )
        .select_related("user")
    )

    recipients = []
    seen_user_ids = set()

    for membership in memberships:
        user = membership.user
        if not user or not user.is_active:
            continue
        if exclude_user_id and user.id == exclude_user_id:
            continue
        if user.id in seen_user_ids:
            continue
        recipients.append(user)
        seen_user_ids.add(user.id)

    return recipients



# =========================================================
# FCM DEVICE TOKEN — REGISTER / UPDATE
# =========================================================
class DeviceTokenRegisterAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):

        serializer = DeviceTokenRegisterSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                    "data": None
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        token = serializer.validated_data["token"]
        device_type = serializer.validated_data["device_type"]

        device_token, created = DeviceToken.objects.update_or_create(
            token=token,
            defaults={
                "user": request.user,
                "device_type": device_type,
                "is_active": True
            }
        )

        return Response(
            {
                "status": True,
                "message": (
                    "Device token registered successfully."
                    if created
                    else "Device token updated successfully."
                ),
                "data": {
                    "id": device_token.id,
                    "device_type": device_token.device_type,
                    "is_active": device_token.is_active
                }
            },
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            )
        )


# =========================================================
# NOTIFICATIONS
# =========================================================
class NotificationListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        queryset = Notification.objects.filter(
            recipient=request.user,
        )

        unread_only = request.data.get("unread_only", False)
        if isinstance(unread_only, str):
            unread_only = unread_only.lower() in ("true", "1", "yes")
        if unread_only:
            queryset = queryset.filter(is_read=False)

        event_prefix = request.data.get("event_prefix")
        if event_prefix:
            queryset = queryset.filter(
                event_code__startswith=event_prefix.strip().upper()
            )

        try:
            limit = int(request.data.get("limit", 50))
        except (TypeError, ValueError):
            limit = 50
        if limit < 1:
            limit = 50
        if limit > 200:
            limit = 200

        before_id = request.data.get("before_id")
        if before_id is not None:
            try:
                queryset = queryset.filter(id__lt=int(before_id))
            except (TypeError, ValueError):
                return Response(
                    {
                        "status": False,
                        "message": "before_id must be an integer.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        queryset = queryset.order_by("-id")[:limit + 1]
        rows = list(queryset)
        has_more = len(rows) > limit
        rows = rows[:limit]

        serializer = NotificationSerializer(rows, many=True)

        unread_count = Notification.objects.filter(
            recipient=request.user, is_read=False,
        ).count()

        return Response(
            {
                "status": True,
                "message": "Notifications fetched successfully.",
                "data": {
                    "unread_count": unread_count,
                    "notifications": serializer.data,
                    "has_more": has_more,
                },
            },
            status=status.HTTP_200_OK,
        )


class NotificationMarkReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = request.data.get("notification_ids")

        if not isinstance(ids, list) or not ids:
            return Response(
                {
                    "status": False,
                    "message": "notification_ids must be a non-empty list.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        updated = (
            Notification.objects
            .filter(
                recipient=request.user,
                id__in=ids,
                is_read=False,
            )
            .update(is_read=True, read_at=now)
        )

        return Response(
            {
                "status": True,
                "message": f"{updated} notification(s) marked as read.",
                "data": {"updated_count": updated},
            },
            status=status.HTTP_200_OK,
        )


class NotificationMarkAllReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        now = timezone.now()
        updated = (
            Notification.objects
            .filter(recipient=request.user, is_read=False)
            .update(is_read=True, read_at=now)
        )

        return Response(
            {
                "status": True,
                "message": "All notifications marked as read.",
                "data": {"updated_count": updated},
            },
            status=status.HTTP_200_OK,
        )


class NotificationUnreadCountAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        count = Notification.objects.filter(
            recipient=request.user, is_read=False,
        ).count()

        return Response(
            {
                "status": True,
                "message": "Unread count fetched.",
                "data": {"unread_count": count},
            },
            status=status.HTTP_200_OK,
        )


class NotificationDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = request.data.get("notification_ids")

        if not isinstance(ids, list) or not ids:
            return Response(
                {
                    "status": False,
                    "message": "notification_ids must be a non-empty list.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        deleted, _ = (
            Notification.objects
            .filter(recipient=request.user, id__in=ids)
            .delete()
        )

        return Response(
            {
                "status": True,
                "message": f"{deleted} notification(s) deleted.",
                "data": {"deleted_count": deleted},
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# ANNOUNCEMENT — CREATE
# =========================================================
class AnnouncementCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        if not _can_manage_announcements(request, organization):
            return Response(
                {
                    "status": False,
                    "message": "You do not have permission to perform this action.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        data = request.data.copy()
        data.pop("organization_id", None)

        serializer = AnnouncementWriteSerializer(data=data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        announcement = serializer.save(
            organization=organization,
            created_by=request.user,
            updated_by=request.user,
        )

        uploaded_attachments = []

        for file in request.FILES.getlist("attachments"):
            file_path = upload_to_s3(
                file=file,
                folder="announcements/attachments",
            )

            attachment = AnnouncementAttachment.objects.create(
                announcement=announcement,
                file=file_path,
                title=file.name,
                uploaded_by=request.user,
            )

            uploaded_attachments.append(
                {
                    "id": attachment.id,
                    "title": attachment.title,
                    "file": (
                        attachment.file.url
                        if attachment.file
                        else None
                    ),
                }
            )

        log_activity(
            request=request,
            action="CREATE",
            module="ANNOUNCEMENT",
            object_type="Announcement",
            object_id=announcement.id,
            description=f"Announcement '{announcement.title}' created.",
            new_data={
                "organization_id": organization.id,
                "title": announcement.title,
                "priority": announcement.priority,
                "is_pinned": announcement.is_pinned,
                "expires_at": (
                    announcement.expires_at.isoformat()
                    if announcement.expires_at
                    else None
                ),
                "attachments": uploaded_attachments,
            },
        )

        # ---- Notify all active org members of the new announcement ----
        recipients = _get_announcement_recipients(
            organization, exclude_user_id=request.user.id
        )

        if recipients:
            # Map announcement priority -> notification priority.
            # URGENT has no Notification equivalent; escalate to HIGH.
            notif_priority = (
                "HIGH" if announcement.priority in ("HIGH", "URGENT")
                else "NORMAL"
            )

            _recipients = recipients
            _announcement_id = announcement.id
            _title = announcement.title
            _body_preview = (
                announcement.description[:140].strip()
                + ("…" if len(announcement.description) > 140 else "")
            )
            _priority = notif_priority
            _is_pinned = announcement.is_pinned

            transaction.on_commit(lambda: notify(
                users=_recipients,
                event_code="ANNOUNCEMENT_PUBLISHED",
                title=(
                    "📌 New pinned announcement"
                    if _is_pinned
                    else "New announcement"
                ),
                body=f"{_title}: {_body_preview}",
                reference_type="announcement",
                reference_id=_announcement_id,
                priority=_priority,
            ))

        return Response(
            {
                "status": True,
                "message": "Announcement created successfully.",
                "data": AnnouncementSerializer(
                    announcement,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


# =========================================================
# ANNOUNCEMENT — LIST (ADMIN)
# =========================================================
class AnnouncementListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        if not _can_manage_announcements(request, organization):
            return Response(
                {
                    "status": False,
                    "message": "You do not have permission to perform this action.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        queryset = (
            Announcement.objects
            .filter(organization=organization)
            .select_related("created_by", "updated_by")
            .prefetch_related("attachments")
        )

        priority = request.data.get("priority")
        is_pinned = request.data.get("is_pinned")
        is_active = request.data.get("is_active")
        search = request.data.get("search")

        if priority:
            queryset = queryset.filter(priority=priority)

        if is_pinned is not None:
            is_pinned_bool = str(is_pinned).lower() in ("true", "1", "yes")
            queryset = queryset.filter(is_pinned=is_pinned_bool)

        if is_active is not None:
            is_active_bool = str(is_active).lower() in ("true", "1", "yes")
            queryset = queryset.filter(is_active=is_active_bool)

        if search:
            search = search.strip()
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
            )

        serializer = AnnouncementSerializer(
            queryset,
            many=True,
            context={"request": request},
        )

        return Response(
            {
                "status": True,
                "message": "Announcements fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# ANNOUNCEMENT — UPDATE
# =========================================================
class AnnouncementUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        if not _can_manage_announcements(request, organization):
            return Response(
                {
                    "status": False,
                    "message": "You do not have permission to perform this action.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        announcement_id = request.data.get("announcement_id")
        if not announcement_id:
            return Response(
                {
                    "status": False,
                    "message": "announcement_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        announcement = Announcement.objects.filter(
            id=announcement_id,
            organization=organization,
        ).first()

        if not announcement:
            return Response(
                {
                    "status": False,
                    "message": "Announcement not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        old_data = {
            "title": announcement.title,
            "priority": announcement.priority,
            "is_pinned": announcement.is_pinned,
        }

        data = request.data.copy()
        data.pop("announcement_id", None)
        data.pop("organization_id", None)
        data.pop("remove_attachment_ids", None)
        data.pop("attachments", None)

        serializer = AnnouncementWriteSerializer(
            announcement,
            data=data,
            partial=True,
        )

        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        announcement = serializer.save(updated_by=request.user)

        # Remove attachments
        remove_attachment_ids = request.data.getlist(
            "remove_attachment_ids"
        )

        removed_attachment_ids = []

        for attachment_id in remove_attachment_ids:
            attachment = AnnouncementAttachment.objects.filter(
                id=attachment_id,
                announcement=announcement,
            ).first()

            if not attachment:
                continue

            removed_attachment_ids.append(attachment.id)

            if attachment.file:
                delete_from_s3(attachment.file)

            attachment.delete()

        # Add new attachments
        added_attachments = []

        for file in request.FILES.getlist("attachments"):
            file_path = upload_to_s3(
                file=file,
                folder="announcements/attachments",
            )

            attachment = AnnouncementAttachment.objects.create(
                announcement=announcement,
                file=file_path,
                title=file.name,
                uploaded_by=request.user,
            )

            added_attachments.append(
                {
                    "id": attachment.id,
                    "title": attachment.title,
                    "file": (
                        attachment.file.url
                        if attachment.file
                        else None
                    ),
                }
            )

        new_data = {
            "title": announcement.title,
            "priority": announcement.priority,
            "is_pinned": announcement.is_pinned,
        }

        if removed_attachment_ids:
            new_data["attachments_removed"] = removed_attachment_ids

        if added_attachments:
            new_data["attachments_added"] = added_attachments

        log_activity(
            request=request,
            action="UPDATE",
            module="ANNOUNCEMENT",
            object_type="Announcement",
            object_id=announcement.id,
            description=f"Announcement '{announcement.title}' updated.",
            old_data=old_data,
            new_data=new_data,
        )

        return Response(
            {
                "status": True,
                "message": "Announcement updated successfully.",
                "data": AnnouncementSerializer(
                    announcement,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# ANNOUNCEMENT — DEACTIVATE
# =========================================================
class AnnouncementDeactivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        if not _can_manage_announcements(request, organization):
            return Response(
                {
                    "status": False,
                    "message": "You do not have permission to perform this action.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        announcement_id = request.data.get("announcement_id")
        if not announcement_id:
            return Response(
                {
                    "status": False,
                    "message": "announcement_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        announcement = Announcement.objects.filter(
            id=announcement_id,
            organization=organization,
            is_active=True,
        ).first()

        if not announcement:
            return Response(
                {
                    "status": False,
                    "message": "Announcement not found or already inactive.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        announcement.is_active = False
        announcement.updated_by = request.user
        announcement.save(
            update_fields=["is_active", "updated_by", "updated_at"]
        )

        log_activity(
            request=request,
            action="DELETE",
            module="ANNOUNCEMENT",
            object_type="Announcement",
            object_id=announcement.id,
            description=f"Announcement '{announcement.title}' deactivated.",
            new_data={"is_active": False},
        )

        return Response(
            {
                "status": True,
                "message": "Announcement deactivated successfully.",
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# ANNOUNCEMENT — MY (EMPLOYEE)
# =========================================================
class MyAnnouncementsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        queryset = (
            _active_announcements_qs(organization)
            .select_related("created_by")
            .prefetch_related("attachments")
            .order_by("-is_pinned", "-created_at")
        )

        priority = request.data.get("priority")
        if priority:
            queryset = queryset.filter(priority=priority)

        serializer = MyAnnouncementSerializer(
            queryset,
            many=True,
            context={"request": request},
        )

        return Response(
            {
                "status": True,
                "message": "Announcements fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# PROJECT CHAT — LIST MESSAGES
# =========================================================
class ProjectChatMessagesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        project_id = request.data.get("project_id")
        if not project_id:
            return Response(
                {
                    "status": False,
                    "message": "project_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        permission, project, _allocation, err = get_project_permission(
            request, project_id
        )
        if err:
            return err

        if permission not in ("ADMIN", "HEAD", "MEMBER"):
            return Response(
                {
                    "status": False,
                    "message": "You do not have access to this project's chat.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        settings_obj, _ = ProjectChatSettings.objects.get_or_create(
            project=project,
        )

        queryset = (
            ProjectMessage.objects
            .filter(project=project)
            .select_related("sender", "sender__role")
            .prefetch_related("attachments")
        )

        since_id = request.data.get("since_id")
        before_id = request.data.get("before_id")

        try:
            limit = int(request.data.get("limit", 50))
        except (TypeError, ValueError):
            limit = 50

        if limit < 1:
            limit = 50
        if limit > 200:
            limit = 200

        if since_id is not None:
            try:
                since_id_int = int(since_id)
            except (TypeError, ValueError):
                return Response(
                    {
                        "status": False,
                        "message": "since_id must be an integer.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            queryset = queryset.filter(id__gt=since_id_int).order_by("id")[:limit]
            messages = list(queryset)

        elif before_id is not None:
            try:
                before_id_int = int(before_id)
            except (TypeError, ValueError):
                return Response(
                    {
                        "status": False,
                        "message": "before_id must be an integer.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            queryset = (
                queryset.filter(id__lt=before_id_int)
                .order_by("-id")[:limit]
            )
            messages = list(queryset)
            messages.reverse()

        else:
            queryset = queryset.order_by("-id")[:limit]
            messages = list(queryset)
            messages.reverse()

        serializer = ProjectMessageSerializer(
            messages,
            many=True,
            context={"request": request},
        )

        latest_id = messages[-1].id if messages else None

        return Response(
            {
                "status": True,
                "message": "Messages fetched successfully.",
                "data": {
                    "project_id": project.id,
                    "posting_permission": settings_obj.posting_permission,
                    "can_current_user_post": _can_current_user_post(
                        permission, project
                    ),
                    "messages": serializer.data,
                    "latest_id": latest_id,
                },
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# PROJECT CHAT — SEND MESSAGE
# =========================================================
class ProjectChatSendAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    @transaction.atomic
    def post(self, request):
        project_id = request.data.get("project_id")
        if not project_id:
            return Response(
                {
                    "status": False,
                    "message": "project_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        permission, project, _allocation, err = get_project_permission(
            request, project_id
        )
        if err:
            return err

        if permission not in ("ADMIN", "HEAD", "MEMBER"):
            return Response(
                {
                    "status": False,
                    "message": "You do not have access to this project's chat.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        can_post, reason = _can_post_to_chat(permission, project, request.user)

        if not can_post:
            return Response(
                {
                    "status": False,
                    "message": reason,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ProjectMessageSendSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        message = ProjectMessage.objects.create(
            project=project,
            organization=project.organization,
            sender=request.user,
            body=serializer.validated_data["body"],
        )

        for file in request.FILES.getlist("attachments"):
            file_path = upload_to_s3(
                file=file,
                folder="projects/chat/attachments",
            )

            ProjectMessageAttachment.objects.create(
                message=message,
                file=file_path,
                title=file.name,
            )

        log_activity(
            request=request,
            action="CREATE",
            module="PROJECT_CHAT",
            object_type="ProjectMessage",
            object_id=message.id,
            description=(
                f"Message sent by '{request.user.username}' "
                f"in project '{project.project_name}'."
            ),
            new_data={
                "project_id": project.id,
                "message_id": message.id,
                "body_length": len(message.body),
            },
        )

        return Response(
            {
                "status": True,
                "message": "Message sent successfully.",
                "data": ProjectMessageSerializer(
                    message,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


# =========================================================
# PROJECT CHAT — DELETE MESSAGE
# =========================================================
class ProjectChatDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    SELF_DELETE_WINDOW_MINUTES = 15

    @transaction.atomic
    def post(self, request):
        message_id = request.data.get("message_id")
        if not message_id:
            return Response(
                {
                    "status": False,
                    "message": "message_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        message = (
            ProjectMessage.objects
            .filter(id=message_id, is_deleted=False)
            .select_related("project")
            .first()
        )

        if not message:
            return Response(
                {
                    "status": False,
                    "message": "Message not found or already deleted.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        permission, _project, _allocation, err = get_project_permission(
            request, message.project_id
        )
        if err:
            return err

        can_delete = False

        if permission in ("ADMIN", "HEAD"):
            can_delete = True
        elif permission == "MEMBER" and message.sender_id == request.user.id:
            elapsed = timezone.now() - message.created_at
            if elapsed <= timedelta(minutes=self.SELF_DELETE_WINDOW_MINUTES):
                can_delete = True

        if not can_delete:
            return Response(
                {
                    "status": False,
                    "message": (
                        "You are not allowed to delete this message. "
                        f"Own messages can be deleted within "
                        f"{self.SELF_DELETE_WINDOW_MINUTES} minutes."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        message.is_deleted = True
        message.deleted_by = request.user
        message.save(
            update_fields=["is_deleted", "deleted_by", "updated_at"]
        )

        log_activity(
            request=request,
            action="DELETE",
            module="PROJECT_CHAT",
            object_type="ProjectMessage",
            object_id=message.id,
            description=(
                f"Message #{message.id} deleted in "
                f"project '{message.project.project_name}'."
            ),
            new_data={"is_deleted": True},
        )

        return Response(
            {
                "status": True,
                "message": "Message deleted successfully.",
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# PROJECT CHAT — SETTINGS (GET / UPDATE)
# =========================================================
class ProjectChatSettingsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        project_id = request.data.get("project_id")
        if not project_id:
            return Response(
                {
                    "status": False,
                    "message": "project_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        permission, project, _allocation, err = get_project_permission(
            request, project_id
        )
        if err:
            return err

        if permission != "ADMIN":
            return Response(
                {
                    "status": False,
                    "message": (
                        "Only the organization admin can change chat settings."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        settings_obj, _created = ProjectChatSettings.objects.get_or_create(
            project=project,
        )

        new_permission = request.data.get("posting_permission")

        # No posting_permission in request → GET behavior
        if new_permission is None:
            return Response(
                {
                    "status": True,
                    "message": "Chat settings fetched successfully.",
                    "data": ProjectChatSettingsSerializer(
                        settings_obj,
                        context={"request": request},
                    ).data,
                },
                status=status.HTTP_200_OK,
            )

        valid_choices = {
            choice[0] for choice in ProjectChatSettings.POSTING_PERMISSION_CHOICES
        }

        if new_permission not in valid_choices:
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": {
                        "posting_permission": [
                            (
                                f'"{new_permission}" is not a valid choice. '
                                f"Valid choices: "
                                f"{', '.join(sorted(valid_choices))}"
                            )
                        ]
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_permission = settings_obj.posting_permission

        if old_permission == new_permission:
            return Response(
                {
                    "status": True,
                    "message": "Chat settings unchanged.",
                    "data": ProjectChatSettingsSerializer(
                        settings_obj,
                        context={"request": request},
                    ).data,
                },
                status=status.HTTP_200_OK,
            )

        settings_obj.posting_permission = new_permission
        settings_obj.updated_by = request.user
        settings_obj.save(
            update_fields=[
                "posting_permission",
                "updated_by",
                "updated_at",
            ]
        )

        log_activity(
            request=request,
            action="UPDATE",
            module="PROJECT_CHAT",
            object_type="ProjectChatSettings",
            object_id=settings_obj.id,
            description=(
                f"Chat settings updated for project "
                f"'{project.project_name}': "
                f"{old_permission} → {new_permission}."
            ),
            old_data={"posting_permission": old_permission},
            new_data={"posting_permission": new_permission},
        )

        return Response(
            {
                "status": True,
                "message": "Chat settings updated successfully.",
                "data": ProjectChatSettingsSerializer(
                    settings_obj,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_200_OK,
        )



# =========================================================
# TEST ONLY — FIRE A NOTIFICATION (NO AUTH)
# =========================================================
# ⚠️ DEBUG-ONLY. Delete the URL pattern before shipping.
# =========================================================

from app.accounts.models import User

class TestSendNotificationAPIView(APIView):
    """
    Fire a notification to one or more users for testing.
    No auth. Only works when settings.DEBUG is True.

    POST body:
        {
            "user_ids": [1, 2, 3],          # required, non-empty list
            "event_code": "TEST_NOTIFICATION",  # required
            "title": "Test title",           # required
            "body": "Test body",             # required
            "reference_type": "test",        # optional
            "reference_id": 123,             # optional
            "priority": "NORMAL",            # optional: NORMAL | HIGH
            "send_push": false,              # optional: default false for tests
            "request_user_id": 5             # optional, logged only
        }
    """
    permission_classes = []  # no auth
    authentication_classes = []  # skip JWT/session entirely

    def post(self, request):
        from django.conf import settings as django_settings

        # Hard guard — never allow this in prod.
        if not getattr(django_settings, "DEBUG", False):
            return Response(
                {
                    "status": False,
                    "message": "Test endpoint disabled (DEBUG=False).",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # ---- Validate user_ids ----
        user_ids = request.data.get("user_ids")

        if not isinstance(user_ids, list) or not user_ids:
            return Response(
                {
                    "status": False,
                    "message": "user_ids must be a non-empty list of integers.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user_ids = [int(uid) for uid in user_ids]
        except (TypeError, ValueError):
            return Response(
                {
                    "status": False,
                    "message": "user_ids must contain only integers.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---- Fetch users (must exist and be active) ----
        users = list(
            User.objects
            .filter(id__in=user_ids, is_active=True)
        )

        if not users:
            return Response(
                {
                    "status": False,
                    "message": "No active users found for the given user_ids.",
                    "data": {"requested_ids": user_ids},
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        found_ids = {u.id for u in users}
        missing_ids = [uid for uid in user_ids if uid not in found_ids]

        # ---- Validate event_code / title / body ----
        event_code = (request.data.get("event_code") or "").strip()
        title = (request.data.get("title") or "").strip()
        body = (request.data.get("body") or "").strip()

        errors = {}
        if not event_code:
            errors["event_code"] = ["This field is required."]
        if not title:
            errors["title"] = ["This field is required."]
        if not body:
            errors["body"] = ["This field is required."]

        if errors:
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---- Optional fields ----
        reference_type = request.data.get("reference_type") or None
        reference_id = request.data.get("reference_id")

        if reference_id is not None:
            try:
                reference_id = int(reference_id)
            except (TypeError, ValueError):
                return Response(
                    {
                        "status": False,
                        "message": "reference_id must be an integer or null.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        priority = (request.data.get("priority") or "NORMAL").upper()
        if priority not in ("NORMAL", "HIGH"):
            return Response(
                {
                    "status": False,
                    "message": 'priority must be "NORMAL" or "HIGH".',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        send_push_raw = request.data.get("send_push", False)
        if isinstance(send_push_raw, str):
            send_push = send_push_raw.lower() in ("true", "1", "yes")
        else:
            send_push = bool(send_push_raw)

        request_user_id = request.data.get("request_user_id")

        # ---- Fire the notification ----
        # No transaction.on_commit needed — this is a test endpoint,
        # no surrounding transaction, fire immediately.
        notify(
            users=users,
            event_code=event_code,
            title=title,
            body=body,
            reference_type=reference_type,
            reference_id=reference_id,
            priority=priority,
            send_push=send_push,
        )

        # ---- Return what happened ----
        created = Notification.objects.filter(
            recipient__in=users,
            event_code=event_code,
        ).order_by("-id")[:len(users)]

        return Response(
            {
                "status": True,
                "message": f"Notification sent to {len(users)} user(s).",
                "data": {
                    "requested_user_ids": user_ids,
                    "delivered_to_user_ids": sorted(found_ids),
                    "missing_or_inactive_user_ids": missing_ids,
                    "event_code": event_code,
                    "priority": priority,
                    "send_push": send_push,
                    "request_user_id": request_user_id,
                    "notification_ids": [n.id for n in created],
                },
            },
            status=status.HTTP_200_OK,
        )
