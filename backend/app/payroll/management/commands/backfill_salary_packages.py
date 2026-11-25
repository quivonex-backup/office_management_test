"""
Batch 17: fill annual_ctc / monthly_gross on salary assignments saved
without a package.

    python manage.py backfill_salary_packages --dry-run
    python manage.py backfill_salary_packages
    python manage.py backfill_salary_packages --organization 3

Fixed structures: filled from the structure (default_package_from_structure,
statutory rates as of each assignment's effective_from). Gross-based
structures (balancing / % of gross): listed only; HR sets the CTC or gross
with payroll/assignments/update/.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from app.payroll.models import EmployeeSalaryAssignment
from app.payroll.services import default_package_from_structure


class Command(BaseCommand):
    help = "Fill annual_ctc / monthly_gross on salary assignments that have none."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would change, save nothing.")
        parser.add_argument("--organization", type=int, help="Only this organization id.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        qs = (
            EmployeeSalaryAssignment.objects.filter(annual_ctc__isnull=True, monthly_gross__isnull=True)
            .select_related("organization", "employee", "salary_structure")
            .order_by("organization_id", "employee__employee_code", "effective_from")
        )
        if options.get("organization"):
            qs = qs.filter(organization_id=options["organization"])

        filled, manual = 0, []
        for a in qs:
            label = (f"[org {a.organization_id}] {a.employee.employee_code} assignment {a.id} "
                     f"'{a.salary_structure.name}' from {a.effective_from}")
            try:
                package = default_package_from_structure(a.organization, a.salary_structure, as_of=a.effective_from)
            except ValueError as exc:
                manual.append(f"{label}: {exc}")
                continue
            self.stdout.write(f"{'WOULD FILL' if dry else 'FILLED'} {label}: "
                              f"gross {package['monthly_gross']} / CTC {package['annual_ctc']}")
            if not dry:
                with transaction.atomic():
                    EmployeeSalaryAssignment.objects.filter(pk=a.pk).update(
                        annual_ctc=package["annual_ctc"], monthly_gross=package["monthly_gross"],
                    )
            filled += 1

        for line in manual:
            self.stdout.write(self.style.WARNING(f"NEEDS HR {line}"))
        self.stdout.write(self.style.SUCCESS(
            f"{'Dry run: ' if dry else ''}{filled} assignment(s) {'to fill' if dry else 'filled'}, "
            f"{len(manual)} need a CTC / gross from HR (payroll/assignments/update/)."
        ))
