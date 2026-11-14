import random
from django.utils import timezone


# Used for client_code generation
def generate_client_code():
    date_part = timezone.now().strftime("%y%m%d")

    while True:
        random_part = f"{random.randint(0, 99999):05d}"
        code = f"CLT-{date_part}-{random_part}"

        from app.clients.models import Client

        if not Client.objects.filter(client_code=code).exists():
            return code


# Used for project_code generation
def generate_project_code():
    date_part = timezone.now().strftime("%y%m%d")

    while True:
        random_part = f"{random.randint(0, 99999):05d}"
        code = f"PR-{date_part}-{random_part}"

        from app.projects.models import Project

        if not Project.objects.filter(project_code=code).exists():
            return code


# Used for vendor_code generation
def generate_vendor_code():
    date_part = timezone.now().strftime("%y%m%d")

    while True:
        random_part = f"{random.randint(0, 99999):05d}"
        code = f"VEN-{date_part}-{random_part}"

        from app.vendors.models import Vendor

        if not Vendor.objects.filter(vendor_code=code).exists():
            return code


# Used for expense_number generation
def generate_expense_code():
    date_part = timezone.now().strftime("%y%m%d")

    while True:
        random_part = f"{random.randint(0, 99999):05d}"
        code = f"EXP-{date_part}-{random_part}"

        from app.expenses.models import Expense

        if not Expense.objects.filter(
            expense_number=code
        ).exists():
            return code


# Used for organization_code generation
def generate_organization_code():
    import random
    from django.utils import timezone
    from app.accounts.models import Organization

    date_part = timezone.now().strftime("%y%m%d")

    while True:
        random_part = f"{random.randint(0, 99999):05d}"
        code = f"ORG-{date_part}-{random_part}"

        if not Organization.objects.filter(
            organization_code=code
        ).exists():
            return code
