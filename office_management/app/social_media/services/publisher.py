from django.db import transaction
from django.utils import timezone

from app.social_media.models import (
    SocialAccount,
    SocialPost,
    SocialPublication,
)
from app.social_media.services.facebook import (
    publish_photo_to_facebook,
    publish_text_to_facebook,
    publish_video_to_facebook,
)
from app.social_media.services.instagram import (
    publish_image_to_instagram,
    publish_video_to_instagram,
)


# MEDIA URL
def get_media_url(media):
    """Get the public URL of a SocialPostMedia file."""
    if not media.file:
        return None

    try:
        return media.file.url
    except Exception as exc:
        raise ValueError(f"Unable to get media URL: {str(exc)}") from exc


# ACTIVE FACEBOOK ACCOUNT
def get_facebook_account(post):
    """Get the latest active Facebook account belonging to the post's creator."""
    account = (
        SocialAccount.objects
        .filter(
            platform="FACEBOOK",
            is_active=True,
            created_by=post.created_by,
        )
        .order_by("-created_at")
        .first()
    )
    if not account:
        raise ValueError(
            "No active Facebook account is connected for this user."
        )
    return account


# ACTIVE INSTAGRAM ACCOUNT
def get_instagram_account(post):
    """Get the latest active Instagram account belonging to the post's creator."""
    account = (
        SocialAccount.objects
        .filter(
            platform="INSTAGRAM",
            is_active=True,
            created_by=post.created_by,
        )
        .order_by("-created_at")
        .first()
    )
    if not account:
        raise ValueError(
            "No active Instagram account is connected for this user."
        )
    return account


# FACEBOOK
def publish_to_facebook(post):
    """
    Publish one SocialPost to Facebook.

    Supported:
        No media  -> Text post
        1 IMAGE   -> Single image post
        1 VIDEO   -> Single normal video post

    Not supported:
        Multiple images
        Multiple videos
        Image + video
        Any multiple-media post
        Reels

    Reels/video-specific publishing is handled separately.
    """
    account = get_facebook_account(post)
    media = list(post.media.all().order_by("sort_order"))

    publication, _ = SocialPublication.objects.update_or_create(
        post=post,
        platform="FACEBOOK",
        defaults={"status": "PENDING", "error_message": None},
    )

    try:
        # NO MEDIA
        if not media:
            result = publish_text_to_facebook(
                page_id=account.page_id,
                page_access_token=account.access_token,
                message=post.caption,
            )

        # MULTIPLE MEDIA
        elif len(media) > 1:
            raise ValueError(
                "Facebook publishing supports only one image "
                "or one video per normal post. "
                "Multiple media items are not supported."
            )

        # SINGLE MEDIA
        else:
            item = media[0]
            media_url = get_media_url(item)
            if not media_url:
                raise ValueError(
                    "Facebook media does not have a valid URL."
                )

            # IMAGE
            if item.media_type == "IMAGE":
                result = publish_photo_to_facebook(
                    page_id=account.page_id,
                    page_access_token=account.access_token,
                    image_url=media_url,
                    caption=post.caption,
                )

            # VIDEO
            elif item.media_type == "VIDEO":
                result = publish_video_to_facebook(
                    page_id=account.page_id,
                    page_access_token=account.access_token,
                    video_url=media_url,
                    caption=post.caption,
                )

            else:
                raise ValueError(
                    f"Unsupported media type: {item.media_type}"
                )

        # SAVE SUCCESSFUL PUBLICATION
        publication.status = "PUBLISHED"
        publication.platform_post_id = result.get("post_id")
        publication.platform_post_url = None
        publication.error_message = None
        publication.published_at = timezone.now()
        publication.save(
            update_fields=[
                "status",
                "platform_post_id",
                "platform_post_url",
                "error_message",
                "published_at",
                "updated_at",
            ]
        )

        return publication

    # FACEBOOK FAILURE
    except Exception as exc:
        publication.status = "FAILED"
        publication.error_message = str(exc)
        publication.save(
            update_fields=["status", "error_message", "updated_at"]
        )
        raise


# INSTAGRAM
def publish_to_instagram(post):
    """
    Publish one SocialPost to Instagram.

    Supported:
        1 IMAGE -> Normal Instagram image post
        1 VIDEO -> Normal Instagram video post

    Not supported:
        No media
        Multiple images
        Multiple videos
        Image + video
        Carousel
        Reels

    Reels are handled separately.
    """
    account = get_instagram_account(post)
    media = list(post.media.all().order_by("sort_order"))

    publication, _ = SocialPublication.objects.update_or_create(
        post=post,
        platform="INSTAGRAM",
        defaults={"status": "PENDING", "error_message": None},
    )

    try:
        # INSTAGRAM REQUIRES MEDIA
        if not media:
            raise ValueError(
                "Instagram publishing requires one image or one video."
            )

        # MULTIPLE MEDIA
        if len(media) > 1:
            raise ValueError(
                "Instagram publishing supports only one image "
                "or one video per normal post. "
                "Carousel/multiple-media publishing is not handled here."
            )

        # SINGLE MEDIA
        item = media[0]
        media_url = get_media_url(item)
        if not media_url:
            raise ValueError(
                "Instagram media does not have a valid URL."
            )

        # IMAGE
        if item.media_type == "IMAGE":
            result = publish_image_to_instagram(
                instagram_user_id=account.instagram_user_id,
                access_token=account.access_token,
                image_url=media_url,
                caption=post.caption,
            )

        # VIDEO
        elif item.media_type == "VIDEO":
            result = publish_video_to_instagram(
                instagram_user_id=account.instagram_user_id,
                access_token=account.access_token,
                video_url=media_url,
                caption=post.caption,
            )

        else:
            raise ValueError(
                f"Unsupported media type: {item.media_type}"
            )

        # SAVE SUCCESSFUL PUBLICATION
        publication.status = "PUBLISHED"
        publication.platform_post_id = result.get("post_id")
        publication.platform_post_url = None
        publication.error_message = None
        publication.published_at = timezone.now()
        publication.save(
            update_fields=[
                "status",
                "platform_post_id",
                "platform_post_url",
                "error_message",
                "published_at",
                "updated_at",
            ]
        )

        return publication

    # INSTAGRAM FAILURE
    except Exception as exc:
        publication.status = "FAILED"
        publication.error_message = str(exc)
        publication.save(
            update_fields=["status", "error_message", "updated_at"]
        )
        raise


# MAIN PUBLISH FUNCTION
@transaction.atomic
def publish_post(post, platforms):
    """
    Publish a SocialPost to the requested platforms.

    Example:
        platforms = ["FACEBOOK", "INSTAGRAM"]

    Each platform is processed independently.

    Possible final post statuses:
        PUBLISHED -> All requested platforms succeeded.
        PARTIAL   -> At least one succeeded and at least one failed.
        FAILED    -> All requested platforms failed.
    """
    # VALIDATE PLATFORMS
    if not isinstance(platforms, list):
        raise ValueError("Platforms must be a list.")

    if not platforms:
        raise ValueError("At least one platform is required.")

    allowed_platforms = {"FACEBOOK", "INSTAGRAM"}

    # Remove duplicates while preserving order.
    platforms = list(dict.fromkeys(platforms))

    invalid_platforms = [
        p for p in platforms if p not in allowed_platforms
    ]
    if invalid_platforms:
        raise ValueError(
            "Unsupported platform(s): " + ", ".join(invalid_platforms)
        )

    # MARK POST AS PUBLISHING
    post.status = "PUBLISHING"
    post.save(update_fields=["status", "updated_at"])

    results = []

    # PUBLISH PLATFORM BY PLATFORM
    for platform in platforms:
        try:
            if platform == "FACEBOOK":
                publication = publish_to_facebook(post)
            elif platform == "INSTAGRAM":
                publication = publish_to_instagram(post)

            results.append(
                {
                    "platform": platform,
                    "success": True,
                    "publication_id": publication.id,
                    "platform_post_id": publication.platform_post_id,
                    "platform_post_url": publication.platform_post_url,
                }
            )

        except Exception as exc:
            results.append(
                {
                    "platform": platform,
                    "success": False,
                    "publication_id": None,
                    "platform_post_id": None,
                    "platform_post_url": None,
                    "error": str(exc),
                }
            )

    # CALCULATE FINAL POST STATUS
    successful_count = sum(1 for r in results if r["success"])
    failed_count = sum(1 for r in results if not r["success"])

    if successful_count > 0 and failed_count > 0:
        post.status = "PARTIAL"
    elif successful_count > 0:
        post.status = "PUBLISHED"
    else:
        post.status = "FAILED"

    post.save(update_fields=["status", "updated_at"])

    return {"post": post, "results": results}