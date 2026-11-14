
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
