import logging

from firebase_admin import messaging

from .models import Notification, DeviceToken
from .firebase import get_firebase_app


logger = logging.getLogger(__name__)


# =========================================================
# FCM SEND
# =========================================================
def _send_fcm_to_user(user, title, body, data):
    """
    Send FCM to all active device tokens for a user.
    Never raises. Auto-deactivates dead tokens.
    """
    tokens = list(
        DeviceToken.objects
        .filter(user=user, is_active=True)
        .values_list("token", flat=True)
    )

    if not tokens:
        return

    try:
        get_firebase_app()
    except Exception:
        logger.exception(
            "FCM unavailable — skipping push for user=%s", user.id,
        )
        return

    for token in tokens:
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data={k: str(v) for k, v in data.items()},
                token=token,
            )
            messaging.send(message)
        except messaging.UnregisteredError:
            DeviceToken.objects.filter(token=token).update(is_active=False)
        except Exception:
            logger.exception(
                "FCM send failed for user=%s token=%s",
                user.id, token[:20],
            )


# =========================================================
# NOTIFY — MAIN ENTRY POINT
# =========================================================
def notify(
    users,
    event_code,
    title,
    body,
    reference_type=None,
    reference_id=None,
    priority="NORMAL",
    send_push=True,
):
    """
    Create Notification rows and send FCM push.
    Never raises. Call via transaction.on_commit() to avoid
    blocking the caller's transaction.

    Args:
        users: single User or list of Users
        event_code: "LEAVE_APPROVED" etc.
        title: short display text
        body: longer text
        reference_type: "leave_application" etc. (for deep-linking)
        reference_id: ID of the referenced object
        priority: "NORMAL" | "HIGH"
        send_push: False to skip FCM (e.g. bulk sends)
    """
    if not isinstance(users, (list, tuple)):
        users = [users]

    users = [u for u in users if u is not None]
    if not users:
        return

    try:
        notifications = Notification.objects.bulk_create([
            Notification(
                recipient=user,
                event_code=event_code,
                title=title,
                body=body,
                reference_type=reference_type,
                reference_id=reference_id,
                priority=priority,
            )
            for user in users
        ])
    except Exception:
        logger.exception(
            "Notification bulk_create failed for event=%s", event_code,
        )
        return

    if not send_push:
        return

    push_data = {
        "event_code": event_code,
        "reference_type": reference_type or "",
        "reference_id": reference_id or "",
        "priority": priority,
    }

    for notification, user in zip(notifications, users):
        _send_fcm_to_user(
            user=user,
            title=title,
            body=body,
            data={**push_data, "notification_id": notification.id},
        )
