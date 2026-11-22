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


# =========================================================
# DECLARATIVE CHECK FOR CLASS-BASED VIEWS (batch 2)
#
#   class ShiftCreateAPIView(AttendanceBaseAPIView):
#       required_perms = ("settings.manage",)     # caller needs ANY of these
#
# Runs before the handler; answers with the normal envelope
# ({"status": false, "message": ...}) and status 403 / the organization
# error from get_user_organization. Views without required_perms are untouched.
# =========================================================
class _EarlyResponse(Exception):
    def __init__(self, response):
        super().__init__("early response")
        self.response = response


class RequiredPermsMixin:
    required_perms = ()

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not self.required_perms:
            return
        from common.services import get_user_organization

        organization, error = get_user_organization(request)
        if error is not None:
            raise _EarlyResponse(error)
        if not has_any_perm(request, organization, self.required_perms):
            raise _EarlyResponse(permission_denied())

    def handle_exception(self, exc):
        if isinstance(exc, _EarlyResponse):
            return exc.response
        return super().handle_exception(exc)


# =========================================================
# SCOPE: self | team | all  (batch 2)
# team = the caller + everyone below them via Employee.reports_to
# =========================================================
VALID_SCOPES = ("all", "team", "self")


class ScopeResult:
    """scope: 'all' | 'team' | 'self'; employee_ids: None (= everyone) or list."""

    def __init__(self, scope, employee_ids, employee):
        self.scope = scope
        self.employee_ids = employee_ids
        self.employee = employee

    def allows(self, employee_id):
        return self.employee_ids is None or employee_id in self.employee_ids

    def filter(self, queryset, field="employee_id"):
        if self.employee_ids is None:
            return queryset
        return queryset.filter(**{f"{field}__in": self.employee_ids})


def resolve_scope(request, organization, requested=None, self_code=None, team_code=None, all_code=None):
    """
    Clamp the requested scope to what the caller may see.

    - requested empty  -> the widest allowed scope
    - requested higher than allowed -> the next lower allowed scope
      (never higher than requested)
    - 'self' needs an Employee row (and self_code when given)
    - 'team' needs team_code and an Employee row
    - 'all'  needs all_code (organization owner always has it)

    Returns (ScopeResult, None) or (None, error Response).
    """
    from common.services import get_team_employee_ids

    requested = (requested or "").strip().lower() if isinstance(requested, str) else requested
    if requested and requested not in VALID_SCOPES:
        return None, Response(
            {"status": False, "message": "scope must be self, team or all."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    employee = get_user_employee(request.user, organization)
    allowed = {
        "all": bool(all_code) and has_perm(request, organization, all_code),
        "team": bool(team_code) and employee is not None and has_perm(request, organization, team_code),
        "self": employee is not None and (self_code is None or has_perm(request, organization, self_code)),
    }

    start = VALID_SCOPES.index(requested) if requested else 0
    for scope in VALID_SCOPES[start:]:
        if not allowed[scope]:
            continue
        if scope == "all":
            return ScopeResult("all", None, employee), None
        if scope == "team":
            return ScopeResult("team", get_team_employee_ids(employee), employee), None
        return ScopeResult("self", [employee.id], employee), None

    return None, permission_denied()


def own_request_denied():
    return Response(
        {"status": False, "message": "You cannot review your own request."},
        status=status.HTTP_403_FORBIDDEN,
    )


def out_of_scope_denied():
    return Response(
        {"status": False, "message": "This record is outside your team."},
        status=status.HTTP_403_FORBIDDEN,
    )


class SuperAdminOnlyMixin:
    """Platform master data (location lists): super admin only (batch 4)."""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        user = request.user
        if not (user and user.is_authenticated and user.is_active and user.is_superuser):
            raise _EarlyResponse(Response(
                {"status": False, "message": "Only the super admin can change master data."},
                status=status.HTTP_403_FORBIDDEN,
            ))

    def handle_exception(self, exc):
        if isinstance(exc, _EarlyResponse):
            return exc.response
        return super().handle_exception(exc)
