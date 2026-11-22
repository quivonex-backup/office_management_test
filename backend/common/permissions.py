"""
Organization-level permission checks.

- accounts.Role (Admin / Employee) is untouched and not used here.
- The organization owner has every permission.
- Any other user: the permissions of the AccessRole on their Employee
  record in this organization, plus the self-service codes.
- Super admin gets no implicit access to organization data.

Usage in a view (after get_user_organization):

    denied = require_perm(request, organization, "employee.update")
    if denied:
        return denied
"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app.accounts.permission_catalog import ALL_CODES, SELF_SERVICE_CODES


def is_org_owner(user, organization):
    return bool(organization and user and organization.owner_id == user.id)


def get_user_employee(user, organization):
    """Active Employee row of `user` in `organization`, or None."""
    if not organization or not user or not user.is_authenticated:
        return None
    from app.employees.models import Employee

    return (
        Employee.objects.select_related("access_role")
        .filter(user=user, organization=organization, is_active=True)
        .first()
    )


def get_permission_codes(user, organization):
    """Sorted list of permission codes the user has in the organization."""
    if not organization or not user or not user.is_authenticated:
        return []

    if is_org_owner(user, organization):
        return sorted(ALL_CODES)

    codes = set()
    employee = get_user_employee(user, organization)
    if employee:
        codes.update(SELF_SERVICE_CODES)
        role = employee.access_role
        if role and role.is_active and role.organization_id == organization.id:
            codes.update(role.permissions.values_list("code", flat=True))
    return sorted(codes)


def has_perm(request, organization, code):
    """True if the caller has `code`. Cached per request."""
    cache = getattr(request, "_perm_cache", None)
    if cache is None:
        cache = {}
        try:
            request._perm_cache = cache
        except AttributeError:
            pass
    key = organization.id if organization else None
    if key not in cache:
        cache[key] = set(get_permission_codes(request.user, organization))
    return code in cache[key]


def has_any_perm(request, organization, codes):
    return any(has_perm(request, organization, c) for c in codes)


def permission_denied():
    return Response(
        {
            "status": False,
            "message": "You do not have permission to perform this action.",
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def require_perm(request, organization, *codes):
    """None if the caller has ANY of `codes`, else a 403 Response."""
    if has_any_perm(request, organization, codes):
        return None
    return permission_denied()


class OrgAPIView(APIView):
    """Small base for organization-scoped POST views (envelope helpers)."""

    permission_classes = [IsAuthenticated]

    @staticmethod
    def ok(message, data=None, http_status=status.HTTP_200_OK):
        body = {"status": True, "message": message}
        if data is not None:
            body["data"] = data
        return Response(body, status=http_status)

    @staticmethod
    def fail(message, errors=None, http_status=status.HTTP_400_BAD_REQUEST):
        body = {"status": False, "message": message}
        if errors is not None:
            body["errors"] = errors
        return Response(body, status=http_status)

    @staticmethod
    def parse_bool(value):
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes")
