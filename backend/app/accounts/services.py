from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def is_super_admin(user):
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and user.is_superuser
    )


def send_user_registration_email(user, plain_password):
    """
    Send account credentials to a newly registered user.

    Important:
    plain_password is used only for sending the email.
    It is never stored in the database.
    """

    site_url = settings.FRONTEND_URL

    context = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "email": user.email,
        "password": plain_password,
        "site_url": site_url,
    }

    html_content = render_to_string(
        "user_registration.html",
        context
    )

    text_content = f"""
Hello {user.first_name or user.username},

Your Project Management ERP account has been created successfully.

Login Details:

Email: {user.email}
Username: {user.username}
Password: {plain_password}

Login URL:
{site_url}

Please keep your credentials secure.

Regards,
Project Management ERP Team
"""

    email = EmailMultiAlternatives(
        subject="Your Project Management ERP Account",
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )

    email.attach_alternative(
        html_content,
        "text/html"
    )

    email.send(fail_silently=False)

# =========================================================
# ORGANIZATION DEFAULTS (batch 1)
# =========================================================
def sync_permissions():
    """Make the Permission table match permission_catalog.PERMISSIONS."""
    from .models import Permission
    from .permission_catalog import PERMISSIONS

    for code, group, label in PERMISSIONS:
        Permission.objects.update_or_create(
            code=code, defaults={"group": group, "label": label}
        )


def seed_organization_defaults(organization, created_by=None):
    """
    Create the four default access roles for a new organization.
    Existing roles with the same name are left untouched.
    Returns the list of AccessRole rows created.
    """
    from .models import AccessRole, AccessRolePermission, Permission
    from .permission_catalog import DEFAULT_ACCESS_ROLES

    sync_permissions()
    by_code = {p.code: p for p in Permission.objects.all()}

    created_roles = []
    for name, spec in DEFAULT_ACCESS_ROLES.items():
        role, created = AccessRole.objects.get_or_create(
            organization=organization,
            name=name,
            defaults={
                "description": spec["description"],
                "created_by": created_by,
                "updated_by": created_by,
            },
        )
        if not created:
            continue
        AccessRolePermission.objects.bulk_create(
            [AccessRolePermission(access_role=role, permission=by_code[c]) for c in spec["codes"]]
        )
        created_roles.append(role)
    return created_roles
