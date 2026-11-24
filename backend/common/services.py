
from rest_framework import status
from rest_framework.response import Response

from app.accounts.models import Organization, OrganizationMembership


def get_user_organization(request):
    memberships = OrganizationMembership.objects.filter(
        user=request.user,
        is_active=True,
        organization__is_active=True,
    ).select_related("organization")

    organization_id = request.data.get("organization_id")

    if organization_id:
        membership = memberships.filter(
            organization_id=organization_id
        ).first()

        if not membership:
            return None, Response(
                {
                    "status": False,
                    "message": "Organization not found or access denied.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return membership.organization, None

    organization_ids = memberships.values_list(
        "organization_id", flat=True
    ).distinct()

    count = organization_ids.count()

    if count == 0:
        return None, Response(
            {
                "status": False,
                "message": "No active organization membership found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    if count > 1:
        return None, Response(
            {
                "status": False,
                "message": (
                    "organization_id is required because you belong "
                    "to multiple organizations."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    organization = Organization.objects.get(
        id=organization_ids.first()
    )

    return organization, None


def get_current_employee(request):
    """
    Resolve the employee linked to the authenticated user.
    Returns (employee, error_response).
    """
    from rest_framework import status
    from rest_framework.response import Response

    employee = getattr(request.user, "employee_profile", None)

    if not employee:
        return None, Response(
            {
                "status": False,
                "message": "No employee profile linked to your account.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    if not employee.is_active:
        return None, Response(
            {
                "status": False,
                "message": "Your employee profile is inactive.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    return employee, None


def get_project_permission(request, project_id):
    """
    Resolve caller's permission on a project.
    Returns (permission, project, allocation, error_response).

    permission: 'ADMIN' | 'HEAD' | 'MEMBER' | None
    """
    from rest_framework import status
    from rest_framework.response import Response

    from app.projects.models import Project, ProjectTeamAllocation

    if not project_id:
        return None, None, None, Response(
            {"status": False, "message": "project_id is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    project = (
        Project.objects
        .filter(id=project_id, is_active=True)
        .select_related("organization", "client")
        .first()
    )

    if not project:
        return None, None, None, Response(
            {"status": False, "message": "Project not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    user = request.user

    # The platform super admin manages organizations, not their project data:
    # no special access here (batch 9). Same rules as everyone else below.

    # Organization owner — ADMIN on all projects in their org.
    if project.organization_id and project.organization.owner_id == user.id:
        return "ADMIN", project, None, None

    # Access role with project.manage — ADMIN on the organization's projects.
    from common.permissions import get_permission_codes

    if project.organization_id and "project.manage" in get_permission_codes(user, project.organization):
        return "ADMIN", project, None, None

    employee = getattr(user, "employee_profile", None)
    if employee and employee.organization_id == project.organization_id:
        allocation = ProjectTeamAllocation.objects.filter(
            project=project,
            employee=employee,
            is_active=True,
        ).first()
        if allocation:
            if allocation.is_project_head:
                return "HEAD", project, allocation, None
            return "MEMBER", project, allocation, None

    return None, project, None, Response(
        {
            "status": False,
            "message": "You do not have access to this project.",
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def get_accessible_projects(request):
    """
    Resolve the set of projects the caller can see, for cross-project listing.

    Returns (projects_qs, permission_map, error_response).

    permission_map: {project_id: 'ADMIN' | 'HEAD' | 'MEMBER'}
    """
    from rest_framework import status
    from rest_framework.response import Response

    from app.projects.models import Project, ProjectTeamAllocation

    user = request.user

    # The platform super admin gets no projects here (batch 9): projects, tasks
    # and project chat belong to the organization.

    # Build scope: orgs the user owns + orgs they are active members of.
    from app.accounts.models import OrganizationMembership

    memberships = (
        OrganizationMembership.objects
        .filter(user=user, is_active=True, organization__is_active=True)
        .select_related("organization")
    )

    # Organizations where the caller is the owner → ADMIN on all projects.
    owned_org_ids = list(
        memberships
        .filter(organization__owner_id=user.id)
        .values_list("organization_id", flat=True)
    )

    # Organizations the user belongs to as a plain member.
    member_org_ids = list(
        memberships
        .exclude(organization__owner_id=user.id)
        .values_list("organization_id", flat=True)
    )

    # Members whose access role has project.manage are ADMIN there too.
    from common.permissions import get_permission_codes

    for membership in memberships.exclude(organization__owner_id=user.id):
        if "project.manage" in get_permission_codes(user, membership.organization):
            owned_org_ids.append(membership.organization_id)
            member_org_ids.remove(membership.organization_id)

    project_ids = set()
    permission_map = {}

    # ADMIN projects (owned orgs).
    if owned_org_ids:
        admin_projects = Project.objects.filter(
            organization_id__in=owned_org_ids, is_active=True
        ).values_list("id", flat=True)
        for pid in admin_projects:
            project_ids.add(pid)
            permission_map[pid] = "ADMIN"

    # HEAD/MEMBER projects (member orgs).
    employee = getattr(user, "employee_profile", None)
    if employee and employee.organization_id in member_org_ids:
        allocations = (
            ProjectTeamAllocation.objects
            .filter(
                employee=employee,
                is_active=True,
                project__is_active=True,
                project__organization_id__in=member_org_ids,
            )
            .values_list("project_id", "is_project_head")
        )
        for pid, is_head in allocations:
            project_ids.add(pid)
            permission_map[pid] = "HEAD" if is_head else "MEMBER"

    if not project_ids:
        return Project.objects.none(), {}, Response(
            {
                "status": False,
                "message": "You do not have access to any projects.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    projects = Project.objects.filter(id__in=project_ids, is_active=True)
    return projects, permission_map, None


# =========================================================
# REPORTING LINE (Employee.reports_to)
# =========================================================
def get_team_employee_ids(employee, include_self=True):
    """
    IDs of everyone below `employee` via reports_to (recursive), limited to
    active employees of the same organization. Iterative; safe against
    accidental cycles.
    """
    from app.employees.models import Employee

    if employee is None:
        return []

    seen = {employee.id}
    frontier = [employee.id]
    while frontier:
        children = list(
            Employee.objects.filter(
                organization_id=employee.organization_id,
                reports_to_id__in=frontier,
                is_active=True,
            )
            .exclude(id__in=seen)
            .values_list("id", flat=True)
        )
        seen.update(children)
        frontier = children

    if not include_self:
        seen.discard(employee.id)
    return sorted(seen)


def would_create_reporting_cycle(employee, new_manager):
    """True if setting employee.reports_to = new_manager makes a loop."""
    if employee is None or new_manager is None:
        return False
    if employee.id is not None and employee.id == new_manager.id:
        return True

    current = new_manager
    hops = 0
    while current is not None and hops < 1000:
        if employee.id is not None and current.reports_to_id == employee.id:
            return True
        current = current.reports_to
        hops += 1
    return False
