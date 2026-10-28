import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.db.models import Model

from .models import ActivityLog


SENSITIVE_FIELDS = {
    "password", "old_password", "new_password", "confirm_password",
    "otp", "otp_hash", "access", "refresh", "token",
    "access_token", "refresh_token", "authorization",
}


def get_client_ip(request):
    """Extract client IP from request, respecting proxies."""
    if not request:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def get_user_agent(request):
    """Return the user-agent string from the request."""
    if not request:
        return None
    return request.META.get("HTTP_USER_AGENT", "")


def is_sensitive_field(field_name):
    """Check if a field name is considered sensitive."""
    if not field_name:
        return False
    return field_name.lower() in SENSITIVE_FIELDS


def clean_sensitive_data(data):
    """
    Replace sensitive values with '********' in dicts/lists.
    Recursively processes nested structures.
    """
    if data is None:
        return None

    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            if is_sensitive_field(key):
                cleaned[key] = "********"
            else:
                cleaned[key] = clean_sensitive_data(value)
        return cleaned

    if isinstance(data, list):
        return [clean_sensitive_data(item) for item in data]

    if isinstance(data, tuple):
        return [clean_sensitive_data(item) for item in data]

    return data


def make_json_safe(data):
    """
    Convert data into JSON‑serialisable types.
    Handles datetime, Decimal, UUID, Django models, etc.
    """
    if data is None:
        return None

    if isinstance(data, (str, int, float, bool)):
        return data

    if isinstance(data, (datetime, date)):
        return data.isoformat()

    if isinstance(data, Decimal):
        return str(data)

    if isinstance(data, UUID):
        return str(data)

    if isinstance(data, Model):
        return {"id": str(data.pk), "value": str(data)}

    if isinstance(data, dict):
        return {str(k): make_json_safe(v) for k, v in data.items()}

    if isinstance(data, (list, tuple, set)):
        return [make_json_safe(item) for item in data]

    if hasattr(data, "name"):
        return {"file_name": str(data.name)}

    # Fallback – try to JSON‑serialise, else convert to string
    try:
        json.dumps(data)
        return data
    except (TypeError, ValueError):
        return str(data)


def prepare_audit_data(data):
    """Clean sensitive data and make it JSON‑safe."""
    if data is None:
        return None
    return make_json_safe(clean_sensitive_data(data))


def log_activity(
    request=None,
    action="OTHER",
    module=None,
    object_type=None,
    object_id=None,
    description=None,
    old_data=None,
    new_data=None,
    user=None,
):
    """
    Central logging function to create an ActivityLog entry.

    The authenticated user is taken from request.user unless
    explicitly provided via the `user` parameter.
    """
    try:
        # Determine the user
        audit_user = user
        if audit_user is None and request:
            request_user = getattr(request, "user", None)
            if request_user and request_user.is_authenticated:
                audit_user = request_user

        # Normalise object_id to string
        if object_id is not None:
            object_id = str(object_id)

        # Extract request metadata
        ip_address = None
        user_agent = None
        request_method = None
        request_path = None

        if request:
            ip_address = get_client_ip(request)
            user_agent = get_user_agent(request)
            request_method = getattr(request, "method", None)
            try:
                request_path = request.get_full_path()
            except Exception:
                request_path = getattr(request, "path", None)

        # Prepare old/new data
        safe_old_data = prepare_audit_data(old_data)
        safe_new_data = prepare_audit_data(new_data)

        # Create the log entry
        activity = ActivityLog.objects.create(
            user=audit_user,
            action=action,
            module=module,
            object_type=object_type,
            object_id=object_id,
            description=description,
            old_data=safe_old_data,
            new_data=safe_new_data,
            ip_address=ip_address,
            user_agent=user_agent,
            request_method=request_method,
            request_path=request_path,
        )
        return activity

    except Exception as error:
        # Audit failures should not break the main business logic
        print(f"Audit logging failed: {error}")
        return None