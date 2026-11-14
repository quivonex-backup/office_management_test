from celery import shared_task
from django.db import transaction

from .models import SocialPost
from .services.publisher import publish_post


@shared_task(
    bind=True,
)
def publish_scheduled_social_post(self, post_id, platforms):
    """
    Publish a scheduled social media post.

    The task first atomically claims the scheduled post.
    This prevents duplicate execution if the same Celery task
    is delivered more than once.
    """

    # ---------------------------------------------------------
    # 1. Atomically claim the scheduled post
    # ---------------------------------------------------------
    try:
        with transaction.atomic():
            post = (
                SocialPost.objects
                .select_for_update()
                .get(id=post_id)
            )

            # Important:
            # This also protects against an already revoked/
            # unscheduled task reaching the worker.
            if post.status != "SCHEDULED":
                return {
                    "success": False,
                    "message": (
                        f"Post is not scheduled. "
                        f"Current status: {post.status}"
                    ),
                    "post_id": post_id,
                }

            post.status = "PUBLISHING"

            post.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

    except SocialPost.DoesNotExist:
        return {
            "success": False,
            "message": "Social post does not exist.",
            "post_id": post_id,
        }

    # ---------------------------------------------------------
    # 2. Publish outside the DB transaction
    # ---------------------------------------------------------
    try:
        result = publish_post(
            post=post,
            platforms=platforms,
        )

        post.refresh_from_db()

        post.celery_task_id = None

        post.save(
            update_fields=[
                "celery_task_id",
                "updated_at",
            ]
        )

        return {
            "success": True,
            "post_id": post_id,
            "status": post.status,
            "results": result.get("results", []),
        }

    except Exception as exc:
        post.refresh_from_db()

        post.status = "FAILED"
        post.celery_task_id = None

        post.save(
            update_fields=[
                "status",
                "celery_task_id",
                "updated_at",
            ]
        )

        return {
            "success": False,
            "message": "Failed to publish scheduled post.",
            "post_id": post_id,
            "status": post.status,
            "error": str(exc),
        }

