import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core import signing
from django.http import JsonResponse
from django.shortcuts import redirect

from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    SocialAccount,
    SocialPost,
    SocialPostMedia,
    SocialPublication,
)
from .serializers import (
    SocialAccountSerializer,
    SocialAccountListSerializer,
    SocialAccountActionSerializer,
    SocialAccountMediaListSerializer,
    SocialPostSerializer,
    SocialPostActionSerializer,
    SocialPostListSerializer,
    SocialPublishSerializer,
    SocialScheduleSerializer,
    SocialPublicationSerializer,
    SocialPublicationActionSerializer,
)
from .tasks import publish_scheduled_social_post
from celery import current_app
from .services.authentication import (
    MetaOAuthAuthentication,
    META_OAUTH_STATE_SALT,
)
from .services.s3_service import (
    upload_to_s3,
    update_s3_file,
    delete_from_s3,
)
from .services.meta_oauth import (
    get_meta_login_url,
    connect_meta_account,
)
from .services.publisher import publish_post
from .services.facebook import get_facebook_account_media
from .services.instagram import get_instagram_account_media
from .template_services import (
    render_meta_callback_success,
    render_meta_callback_error,
)

User = get_user_model()


# COMMON RESPONSE HELPERS
def success_response(message, data=None, status_code=status.HTTP_200_OK):
    return Response(
        {"status": True, "message": message, "data": data},
        status=status_code,
    )


def error_response(message, errors=None, status_code=status.HTTP_400_BAD_REQUEST):
    response_data = {"status": False, "message": message}
    if errors is not None:
        response_data["errors"] = errors
    return Response(response_data, status=status_code)


# META CONNECT
class MetaConnectAPIView(APIView):
    """
    Start Meta OAuth connection.

    Requires the application's normal JWT authentication.

    Flow:

        Frontend
            |
            | Authorization: Bearer <JWT>
            v
        This API
            |
            | signed OAuth state
            v
        Meta OAuth
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. Get currently authenticated Django user
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse(
                {"status": False, "message": "Authentication required."},
                status=401,
            )

        # 2. Create signed OAuth state
        #
        # The user ID is stored INSIDE a cryptographically
        # signed value.
        #
        # Do NOT put the JWT itself into the state.
        state = signing.dumps(user.id, salt=META_OAUTH_STATE_SALT)

        # 3. Generate Meta OAuth URL
        authorization_url = get_meta_login_url(state=state)

        # 4. Return URL to frontend
        return success_response(
            message="Meta authorization URL generated.",
            data={"authorization_url": authorization_url},
        )


# META CALLBACK
class MetaCallbackAPIView(APIView):
    """
    Meta OAuth callback.

    Meta redirects the user's browser directly to this URL.

    Example:

        /social_media/meta/callback/
            ?code=XXXXX
            &state=XXXXX

    Normal application JWT authentication is NOT used here.

    Instead, MetaOAuthAuthentication verifies the signed
    OAuth state and identifies the Django user.
    """

    authentication_classes = [MetaOAuthAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. Check whether Meta returned an error
        error = request.GET.get("error")
        if error:
            error_description = request.GET.get(
                "error_description", "Meta authorization failed."
            )
            return JsonResponse(
                {
                    "status": False,
                    "message": error_description,
                    "error": error,
                },
                status=400,
            )

        # 2. Check authorization code
        code = request.GET.get("code")
        if not code:
            return JsonResponse(
                {"status": False, "message": "Authorization code is missing."},
                status=400,
            )

        # 3. request.user comes from MetaOAuthAuthentication
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse(
                {"status": False, "message": "OAuth user authentication failed."},
                status=401,
            )

        # 4. Connect Meta account
        try:
            result = connect_meta_account(user=user, code=code)
        except Exception as exc:
            return JsonResponse(
                {
                    "status": False,
                    "message": "Failed to connect Meta account.",
                    "error": str(exc),
                },
                status=400,
            )

        # 5. Serialize connected accounts
        accounts = result.get("accounts", [])
        serialized_accounts = SocialAccountSerializer(accounts, many=True).data

        # 6. Return success
        # return JsonResponse(
        #     {
        #         "status": True,
        #         "message": "Meta account connected successfully.",
        #         "data": {
        #             "accounts": serialized_accounts,
        #             "pages_found": result.get("pages_found", 0),
        #             "expires_in": result.get("expires_in"),
        #         },
        #     },
        #     status=200,
        # )

        return render_meta_callback_success(
            request=request,
            message="Your Facebook and Instagram accounts have been connected successfully.",
        )


# SOCIAL ACCOUNT LIST
class SocialAccountListAPIView(APIView):
    """
    List connected Facebook / Instagram accounts.
    POST: /api/social/accounts/list/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SocialAccountListSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Validation failed.", errors=serializer.errors
            )

        queryset = SocialAccount.objects.filter(created_by=request.user)
        platform = serializer.validated_data.get("platform")
        is_active = serializer.validated_data.get("is_active")
        if platform:
            queryset = queryset.filter(platform=platform)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        queryset = queryset.order_by("-created_at")

        data = SocialAccountSerializer(queryset, many=True).data
        return success_response(
            message="Social accounts fetched successfully.", data=data
        )


# SOCIAL ACCOUNT ACTIVATE
class SocialAccountActivateAPIView(APIView):
    """
    Activate a connected social account.
    POST: /api/social/accounts/activate/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SocialAccountActionSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Validation failed.", errors=serializer.errors
            )

        account_id = serializer.validated_data["account_id"]
        try:
            account = SocialAccount.objects.get(
                id=account_id, created_by=request.user
            )
        except SocialAccount.DoesNotExist:
            return error_response(
                message="Social account not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        account.is_active = True
        account.save(update_fields=["is_active", "updated_at"])
        return success_response(
            message="Social account activated successfully.",
            data=SocialAccountSerializer(account).data,
        )


# SOCIAL ACCOUNT DEACTIVATE
class SocialAccountDeactivateAPIView(APIView):
    """
    Deactivate a connected social account.
    POST: /api/social/accounts/deactivate/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SocialAccountActionSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Validation failed.", errors=serializer.errors
            )

        account_id = serializer.validated_data["account_id"]
        try:
            account = SocialAccount.objects.get(
                id=account_id, created_by=request.user
            )
        except SocialAccount.DoesNotExist:
            return error_response(
                message="Social account not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        account.is_active = False
        account.save(update_fields=["is_active", "updated_at"])
        return success_response(
            message="Social account deactivated successfully.",
            data=SocialAccountSerializer(account).data,
        )


# SOCIAL ACCOUNT DELETE
class SocialAccountDeleteAPIView(APIView):
    """
    Permanently remove a connected social account.
    POST: /api/social/accounts/delete/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SocialAccountActionSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Validation failed.", errors=serializer.errors
            )

        account_id = serializer.validated_data["account_id"]
        try:
            account = SocialAccount.objects.get(
                id=account_id, created_by=request.user
            )
        except SocialAccount.DoesNotExist:
            return error_response(
                message="Social account not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        account.delete()
        return success_response(
            message="Social account deleted successfully.", data=None
        )


# SOCIAL ACCOUNT MEDIA LIST
class SocialAccountMediaListAPIView(APIView):
    """
    Fetch media/posts from a connected Facebook or Instagram account.
    POST: /api/social/accounts/media/
    First page:
    {
        "account_id": 4,
        "limit": 10
    }
    Next page:
    {
        "account_id": 4,
        "limit": 10,
        "after": "CURSOR"
    }
    Previous page:
    {
        "account_id": 4,
        "limit": 10,
        "before": "CURSOR"
    }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SocialAccountMediaListSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Validation failed.",
                errors=serializer.errors,
            )

        account_id = serializer.validated_data["account_id"]
        limit = serializer.validated_data.get("limit", 25)
        after = serializer.validated_data.get("after")
        before = serializer.validated_data.get("before")

        try:
            account = SocialAccount.objects.get(
                id=account_id,
                created_by=request.user,
                is_active=True,
            )
        except SocialAccount.DoesNotExist:
            return error_response(
                message="Social account not found or inactive.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        try:
            # FACEBOOK
            if account.platform == "FACEBOOK":
                media_data = get_facebook_account_media(
                    page_id=account.page_id or account.account_id,
                    page_access_token=account.access_token,
                    limit=limit,
                    after=after,
                    before=before,
                )

            # INSTAGRAM
            elif account.platform == "INSTAGRAM":
                media_data = get_instagram_account_media(
                    instagram_user_id=account.instagram_user_id or account.account_id,
                    access_token=account.access_token,
                    limit=limit,
                    after=after,
                    before=before,
                )

            else:
                return error_response(
                    message="Unsupported social platform.",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        except Exception as exc:
            return error_response(
                message="Failed to fetch account media.",
                errors={"error": str(exc)},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        paging = media_data.get("paging", {})
        cursors = paging.get("cursors", {})

        return success_response(
            message="Account media fetched successfully.",
            data={
                "account_id": account.id,
                "platform": account.platform,
                "account_name": account.account_name,
                "media": media_data.get("data", []),
                "paging": {
                    "before": cursors.get("before"),
                    "after": cursors.get("after"),
                    "next": paging.get("next"),
                    "previous": paging.get("previous"),
                },
            },
        )


# CREATE SOCIAL POST
class SocialPostCreateAPIView(APIView):
    """
    Create a social media draft post.

    POST: /api/social/posts/create/
    Content-Type: multipart/form-data

    Example:

        caption:
            New property available!

        media:
            image1.jpg
        media_type:
            IMAGE

        OR
            
        media:
            video1.mp4
        media_type:
            VIDEO

    media and media_type must be provided in the same order.
    """

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        caption = request.data.get("caption", "")

        files = request.FILES.getlist("media")
        media_types = request.data.getlist("media_type")

        # Validate media
        if not files:
            media_types = []
        else:
            if not media_types:
                return error_response(
                    message="media_type is required for each media file.",
                    errors={
                        "media_type": [
                            "Provide IMAGE or VIDEO for every uploaded file."
                        ]
                    },
                )

            if len(files) != len(media_types):
                return error_response(
                    message="Number of media_type values must match number of media files.",
                    errors={
                        "media": [f"{len(files)} media files received."],
                        "media_type": [
                            f"{len(media_types)} media_type values received."
                        ],
                    },
                )

            for index, media_type in enumerate(media_types):
                if media_type not in ("IMAGE", "VIDEO"):
                    return error_response(
                        message="Invalid media_type.",
                        errors={
                            "media_type": [
                                f"Item {index + 1} must be IMAGE or VIDEO."
                            ]
                        },
                    )

        # Create post
        post = SocialPost.objects.create(
            caption=caption,
            status="DRAFT",
            created_by=request.user,
        )

        # Upload media
        for index, file in enumerate(files):
            file_path = upload_to_s3(
                file=file,
                folder="social_media/posts",
            )
            if not file_path:
                continue

            SocialPostMedia.objects.create(
                post=post,
                media_type=media_types[index],
                file=file_path,
                sort_order=index,
            )

        # Response
        post_data = SocialPostSerializer(
            post,
            context={"request": request},
        ).data

        return success_response(
            message="Social post created successfully.",
            data=post_data,
            status_code=status.HTTP_201_CREATED,
        )


# SOCIAL POST LIST
class SocialPostListAPIView(APIView):
    """
    List social media posts.
    POST: /api/social/posts/list/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SocialPostListSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Validation failed.", errors=serializer.errors
            )

        queryset = SocialPost.objects.filter(
            created_by=request.user
        ).prefetch_related("media", "publications")

        filter_status = serializer.validated_data.get("status")
        if filter_status:
            queryset = queryset.filter(status=filter_status)
        queryset = queryset.order_by("-created_at")

        page = serializer.validated_data.get("page", 1)
        page_size = serializer.validated_data.get("page_size", 10)
        start = (page - 1) * page_size
        end = start + page_size
        total = queryset.count()
        posts = queryset[start:end]

        data = SocialPostSerializer(
            posts, many=True, context={"request": request}
        ).data
        return success_response(
            message="Social posts fetched successfully.",
            data={
                "results": data,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size,
                },
            },
        )


# SOCIAL POST DETAIL
class SocialPostDetailAPIView(APIView):
    """
    Get one social media post.
    POST: /api/social/posts/detail/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SocialPostActionSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Validation failed.", errors=serializer.errors
            )

        post_id = serializer.validated_data["post_id"]
        try:
            post = (
                SocialPost.objects
                .prefetch_related("media", "publications")
                .get(id=post_id, created_by=request.user)
            )
        except SocialPost.DoesNotExist:
            return error_response(
                message="Social post not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return success_response(
            message="Social post fetched successfully.",
            data=SocialPostSerializer(
                post, context={"request": request}
            ).data,
        )


# UPDATE SOCIAL POST
class SocialPostUpdateAPIView(APIView):
    """
    Update a social media post.

    If new media is supplied, all existing media is replaced.

    POST: /api/social/posts/update/

    Content-Type: multipart/form-data

    Example:

        post_id:
            1

        caption:
            Updated caption

        media:
            image1.jpg
        media_type:
            IMAGE

        OR
            
        media:
            video1.mp4
        media_type:
            VIDEO
    """

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        post_id = request.data.get("post_id")
        if not post_id:
            return error_response(message="post_id is required.")

        try:
            post = SocialPost.objects.get(id=post_id, created_by=request.user)
        except SocialPost.DoesNotExist:
            return error_response(
                message="Social post not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        # Published posts cannot be edited
        if post.status == "PUBLISHED":
            return error_response(
                message=(
                    "Published posts cannot be updated. "
                    "Create a new post instead."
                )
            )

        # Update caption
        if "caption" in request.data:
            post.caption = request.data.get("caption", "")
            post.save(update_fields=["caption", "updated_at"])

        # Get uploaded media
        files = request.FILES.getlist("media")

        if files:
            media_types = request.data.getlist("media_type")

            # Validate media types
            if not media_types:
                return error_response(
                    message="media_type is required for each media file.",
                    errors={
                        "media_type": [
                            "Provide IMAGE or VIDEO for every uploaded file."
                        ]
                    },
                )

            if len(files) != len(media_types):
                return error_response(
                    message=(
                        "Number of media_type values "
                        "must match number of media files."
                    ),
                    errors={
                        "media": [f"{len(files)} media files received."],
                        "media_type": [
                            f"{len(media_types)} media_type values received."
                        ],
                    },
                )

            for index, media_type in enumerate(media_types):
                if media_type not in ("IMAGE", "VIDEO"):
                    return error_response(
                        message="Invalid media_type.",
                        errors={
                            "media_type": [
                                f"Item {index + 1} must be IMAGE or VIDEO."
                            ]
                        },
                    )

            # Upload new media first
            new_media_paths = []
            for file in files:
                file_path = upload_to_s3(
                    file=file,
                    folder="social_media/posts",
                )
                if file_path:
                    new_media_paths.append(file_path)

            # Delete old media
            existing_media = list(post.media.all())
            for media in existing_media:
                if media.file:
                    delete_from_s3(media.file)
                media.delete()

            # Create new media
            for index, file_path in enumerate(new_media_paths):
                SocialPostMedia.objects.create(
                    post=post,
                    media_type=media_types[index],
                    file=file_path,
                    sort_order=index,
                )

        # Response
        post.refresh_from_db()

        return success_response(
            message="Social post updated successfully.",
            data=SocialPostSerializer(
                post,
                context={"request": request},
            ).data,
        )


# DELETE SOCIAL POST
class SocialPostDeleteAPIView(APIView):
    """
    Delete a social media post.
    POST: /api/social/posts/delete/
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = SocialPostActionSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Validation failed.", errors=serializer.errors
            )

        post_id = serializer.validated_data["post_id"]
        try:
            post = SocialPost.objects.get(id=post_id, created_by=request.user)
        except SocialPost.DoesNotExist:
            return error_response(
                message="Social post not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        media_files = list(post.media.all())
        for media in media_files:
            if media.file:
                delete_from_s3(media.file)

        post.delete()
        return success_response(
            message="Social post deleted successfully.", data=None
        )


# PUBLISH SOCIAL POST
class SocialPostPublishAPIView(APIView):
    """
    Publish a post to Facebook / Instagram.
    POST: /api/social/posts/publish/
    Example:
    {
        "post_id": 1,
        "platforms": ["FACEBOOK", "INSTAGRAM"]
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SocialPublishSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Validation failed.", errors=serializer.errors
            )

        post_id = serializer.validated_data["post_id"]
        platforms = serializer.validated_data["platforms"]

        try:
            post = SocialPost.objects.get(id=post_id, created_by=request.user)
        except SocialPost.DoesNotExist:
            return error_response(
                message="Social post not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if post.status == "PUBLISHED":
            return error_response(
                message="This post has already been published."
            )

        try:
            result = publish_post(post=post, platforms=platforms)
        except Exception as exc:
            return error_response(
                message="Failed to publish social post.",
                errors={"error": str(exc)},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return success_response(
            message="Social post publishing completed.",
            data={
                "post_id": post.id,
                "status": post.status,
                "results": result["results"],
            },
        )


# SCHEDULE SOCIAL POST
class SocialPostScheduleAPIView(APIView):
    """
    Schedule a social media post.

    POST: /api/social/posts/schedule/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SocialScheduleSerializer(
            data=request.data,
            context={"request": request},
        )

        if not serializer.is_valid():
            return error_response(
                message="Validation failed.",
                errors=serializer.errors,
            )

        post_id = serializer.validated_data["post_id"]
        scheduled_at = serializer.validated_data["scheduled_at"]
        platforms = serializer.validated_data["platforms"]

        try:
            with transaction.atomic():
                post = (
                    SocialPost.objects
                    .select_for_update()
                    .get(
                        id=post_id,
                        created_by=request.user,
                    )
                )

                if post.status == "PUBLISHED":
                    return error_response(
                        message="Published post cannot be scheduled."
                    )

                if post.status == "SCHEDULED":
                    return error_response(
                        message="This post is already scheduled."
                    )

                post.scheduled_at = scheduled_at
                post.status = "SCHEDULED"

                post.save(
                    update_fields=[
                        "scheduled_at",
                        "status",
                        "updated_at",
                    ]
                )

                task = publish_scheduled_social_post.apply_async(
                    args=[
                        post.id,
                        platforms,
                    ],
                    eta=scheduled_at,
                )

                post.celery_task_id = task.id

                post.save(
                    update_fields=[
                        "celery_task_id",
                        "updated_at",
                    ]
                )

        except SocialPost.DoesNotExist:
            return error_response(
                message="Social post not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        except Exception as exc:
            return error_response(
                message="Failed to schedule social post.",
                errors={
                    "error": str(exc),
                },
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return success_response(
            message="Social post scheduled successfully.",
            data={
                "post_id": post.id,
                "scheduled_at": post.scheduled_at,
                "platforms": platforms,
                "status": post.status,
                "celery_task_id": task.id,
            },
        )


# UNSCHEDULE SOCIAL POST
class SocialPostUnscheduleAPIView(APIView):
    """
    Remove a post from the schedule.

    POST: /api/social/posts/unschedule/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SocialPostActionSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return error_response(
                message="Validation failed.",
                errors=serializer.errors,
            )

        post_id = serializer.validated_data["post_id"]

        try:
            with transaction.atomic():

                post = (
                    SocialPost.objects
                    .select_for_update()
                    .get(
                        id=post_id,
                        created_by=request.user,
                    )
                )

                if post.status != "SCHEDULED":
                    return error_response(
                        message="This post is not currently scheduled."
                    )

                # Revoke the scheduled Celery task
                if post.celery_task_id:
                    try:
                        current_app.control.revoke(
                            post.celery_task_id,
                            terminate=False,
                        )
                    except Exception:
                        pass

                post.status = "DRAFT"
                post.scheduled_at = None
                post.celery_task_id = None

                post.save(
                    update_fields=[
                        "status",
                        "scheduled_at",
                        "celery_task_id",
                        "updated_at",
                    ]
                )

        except SocialPost.DoesNotExist:
            return error_response(
                message="Social post not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return success_response(
            message="Social post unscheduled successfully.",
            data={
                "post_id": post.id,
                "status": post.status,
                "scheduled_at": None,
            },
        )


# PUBLICATION LIST
class SocialPublicationListAPIView(APIView):
    """
    List publication records.
    POST: /api/social/publications/list/
    Optional:
    {
        "post_id": 1
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        post_id = request.data.get("post_id")
        queryset = (
            SocialPublication.objects
            .filter(post__created_by=request.user)
            .select_related("post")
            .order_by("-created_at")
        )
        if post_id:
            queryset = queryset.filter(post_id=post_id)

        data = SocialPublicationSerializer(queryset, many=True).data
        return success_response(
            message="Publications fetched successfully.", data=data
        )


# PUBLICATION DETAIL
class SocialPublicationDetailAPIView(APIView):
    """
    Get one publication record.
    POST: /api/social/publications/detail/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SocialPublicationActionSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                message="Validation failed.", errors=serializer.errors
            )

        publication_id = serializer.validated_data["publication_id"]
        try:
            publication = (
                SocialPublication.objects
                .select_related("post")
                .get(id=publication_id, post__created_by=request.user)
            )
        except SocialPublication.DoesNotExist:
            return error_response(
                message="Publication not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return success_response(
            message="Publication fetched successfully.",
            data=SocialPublicationSerializer(publication).data,
        )

    