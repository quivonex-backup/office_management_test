
import logging
import secrets
import string

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from rest_framework.exceptions import ValidationError

from app.accounts.models import Role
from .models import Employee


logger = logging.getLogger(__name__)


# def generate_employee_password(length=14):
#     """Generate a random password containing letters, digits and symbols."""

#     alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"

#     while True:
#         password = "".join(
#             secrets.choice(alphabet) for _ in range(length)
#         )

#         if (
#             any(c.islower() for c in password)
#             and any(c.isupper() for c in password)
#             and any(c.isdigit() for c in password)
#             and any(c in "!@#$%^&*()-_=+" for c in password)
#         ):
#             return password

def generate_employee_password(length=14):
    """Return a fixed temporary password for testing."""
    return "user@123"



def _send_employee_account_email(user_id, password, employee_id):
    """Send employee credentials using the HTML email template."""
    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
        employee = Employee.objects.select_related(
            "organization"
        ).get(pk=employee_id)

        organization_name = (
            employee.organization.organization_name
            if employee.organization
            else "Your Organization"
        )

        frontend_url = (settings.FRONTEND_URL or "").rstrip("/")

        context = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "email": user.email,
            "password": password,  # Original plain-text password
            "employee_code": employee.employee_code,
            "organization_name": organization_name,
            "login_url": f"{frontend_url}/login" if frontend_url else "",
        }

        html_message = render_to_string(
            "employee_account_created.html", context
        )

        send_mail(
            subject=f"Your employee account - {organization_name}",
            message=strip_tags(html_message),
            from_email=settings.DEFAULT_FROM_EMAIL, 
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(
            "Employee account email sent for user ID %s, employee ID %s",
            user_id, employee_id,
        )

    except Exception:
        logger.exception(
            "Failed to send employee account email for user ID %s",
            user_id,
        )


def create_employee_user(employee):
    """
    Create and link a User account to an existing Employee.

    Call this inside transaction.atomic().
    Returns (user, generated_password).
    """

    User = get_user_model()

    if employee.user_id:
        raise ValidationError(
            {"employee_id": "This employee already has a user account."}
        )

    email = (employee.personal_email or "").strip().lower()
    mobile = (employee.mobile or "").strip()

    if not email:
        raise ValidationError(
            {"email": "The employee must have a personal email address."}
        )

    if not mobile:
        raise ValidationError(
            {"mobile": "The employee must have a mobile number."}
        )

    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError(
            {"email": "A user account with this email already exists."}
        )

    if User.objects.filter(mobile=mobile).exists():
        raise ValidationError(
            {"mobile": "A user account with this mobile number already exists."}
        )

    try:
        employee_role = Role.objects.get(
            name__iexact="Employee",
            is_active=True,
        )
    except Role.DoesNotExist:
        raise ValidationError(
            {"role": "An active Employee role must exist before account creation."}
        )
    except Role.MultipleObjectsReturned:
        raise ValidationError(
            {"role": "Multiple Employee roles exist. Resolve the duplicate roles."}
        )

    # Use the employee code as the username.
    username = employee.employee_code.lower()

    if User.objects.filter(username__iexact=username).exists():
        raise ValidationError(
            {"username": "The generated employee username is already in use."}
        )

    generated_password = generate_employee_password()

    user = User(
        username=username,
        first_name=employee.first_name,
        last_name=employee.last_name,
        email=email,
        mobile=mobile,
        role=employee_role,
        is_active=True,
    )

    user.set_password(generated_password)
    user.save()

    employee.user = user
    employee.save(update_fields=["user", "updated_at"])

    # Send only after the database transaction has committed.
    transaction.on_commit(
        lambda user_id=user.pk,
        password=generated_password,
        employee_id=employee.pk: _send_employee_account_email(
            user_id,
            password,
            employee_id,
        )
    )

    return user, generated_password
