
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


# =========================================================
# ORGANIZATION ASSIGNMENTS (batch 1)
# branch / department / designation / access role / reporting manager
# =========================================================
ASSIGNMENT_KEYS = ("branch_id", "department_id", "designation_id", "access_role_id", "reports_to_id")


def _is_blank(value):
    return value is None or (isinstance(value, str) and value.strip().lower() in ("", "null", "none"))


def resolve_org_assignments(data, organization, employee=None, can_assign_access=True):
    """
    Validate the assignment keys present in `data` (all optional).
    A blank / null value clears the link.

    Returns (changes, errors):
      changes: {"branch": obj|None, "department_ref": ..., "designation_ref": ...,
                "access_role": ..., "reports_to": ...}  (only keys that were sent)
      errors:  {field: [message]}
    """
    from app.accounts.models import AccessRole, Branch
    from common.services import would_create_reporting_cycle
    from .models import Department, Designation

    lookups = {
        "branch_id": ("branch", Branch, "Branch"),
        "department_id": ("department_ref", Department, "Department"),
        "designation_id": ("designation_ref", Designation, "Designation"),
        "access_role_id": ("access_role", AccessRole, "Access role"),
        "reports_to_id": ("reports_to", Employee, "Reporting manager"),
    }

    changes, errors = {}, {}
    for key in ASSIGNMENT_KEYS:
        if key not in data:
            continue
        attr, model, label = lookups[key]
        value = data.get(key)

        if key == "access_role_id" and not can_assign_access:
            errors[key] = ["You do not have permission to assign access roles."]
            continue

        if _is_blank(value):
            changes[attr] = None
            continue

        try:
            pk = int(value)
        except (TypeError, ValueError):
            errors[key] = [f"{label} id must be a number."]
            continue

        obj = model.objects.filter(pk=pk, organization=organization, is_active=True).first()
        if obj is None:
            errors[key] = [f"Active {label.lower()} not found in this organization."]
            continue
        changes[attr] = obj

    manager = changes.get("reports_to")
    if manager is not None and employee is not None and would_create_reporting_cycle(employee, manager):
        errors["reports_to_id"] = ["This reporting manager would create a reporting loop."]

    return changes, errors


def apply_org_assignments(employee, changes, text_sent=None):
    """
    Apply `changes` from resolve_org_assignments and keep the legacy text
    fields in step. `text_sent` = set of legacy text fields ("department",
    "designation") the client sent without the matching *_id: those are
    linked to a master with the same name when one exists.
    Saves only the changed fields. Returns the list of saved field names.
    """
    from .models import Department, Designation

    fields = []
    for attr, obj in changes.items():
        setattr(employee, attr, obj)
        fields.append(attr)
        if attr == "department_ref":
            employee.department = obj.name if obj else None
            fields.append("department")
        elif attr == "designation_ref":
            employee.designation = obj.name if obj else None
            fields.append("designation")

    for text_field, ref_attr, model in (
        ("department", "department_ref", Department),
        ("designation", "designation_ref", Designation),
    ):
        if text_sent and text_field in text_sent and ref_attr not in changes:
            raw = (getattr(employee, text_field) or "").strip()
            match = (
                model.objects.filter(organization=employee.organization, name__iexact=raw, is_active=True).first()
                if raw else None
            )
            setattr(employee, ref_attr, match)
            fields.append(ref_attr)

    if fields:
        fields = sorted(set(fields)) + ["updated_at"]
        employee.save(update_fields=fields)
    return fields



# =========================================================
# EXIT (batch 4)
# =========================================================
def close_open_assignments(employee, last_working_day):
    """
    End shift and salary assignments that are still running after the last
    working day. Assignments starting after that day are left untouched and
    only counted (delete them yourself if they were planned by mistake).
    """
    from django.db.models import Q

    from app.attendance.models import EmployeeShiftAssignment
    from app.payroll.models import EmployeeSalaryAssignment

    result = {}
    for key, model in (("shift", EmployeeShiftAssignment), ("salary", EmployeeSalaryAssignment)):
        running = model.objects.filter(
            employee=employee, effective_from__lte=last_working_day,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=last_working_day))
        result[f"closed_{key}_assignments"] = running.update(effective_to=last_working_day)
        result[f"future_{key}_assignments"] = model.objects.filter(
            employee=employee, effective_from__gt=last_working_day,
        ).count()
    return result
