"""
One-time / repeatable setup after the batch 1 migrations:

  1. Sync the permission catalog (accounts/permission_catalog.py).
  2. Create the 4 default access roles for every organization that does not
     have them yet (an organization's own edits are never overwritten).
  3. Create Department / Designation rows from the existing free-text
     employee fields (per organization, case-insensitive) and link employees.
     Text fields are not changed. Already linked employees are skipped.

Usage:
    python manage.py seed_org_access            # apply
    python manage.py seed_org_access --dry-run  # show what would happen, change nothing

Safe to run more than once.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from app.accounts.models import Organization
from app.accounts.services import seed_organization_defaults, sync_permissions
from app.employees.models import Department, Designation, Employee


class _DryRun(Exception):
    pass


def _link_text(organization, text_field, ref_field, model):
    """
    Group unlinked employees by trimmed, case-insensitive text. A new master
    row uses the most common spelling (ties: the oldest employee's).
    """
    from collections import Counter, defaultdict

    groups = defaultdict(list)
    qs = Employee.objects.filter(organization=organization, **{f"{ref_field}__isnull": True}).order_by("id")
    for employee in qs:
        raw = (getattr(employee, text_field) or "").strip()
        if raw:
            groups[raw.lower()].append((employee, raw))

    created, linked = 0, 0
    for key, rows in groups.items():
        master = model.objects.filter(organization=organization, name__iexact=key).first()
        if master is None:
            counts = Counter(raw for _e, raw in rows)
            best = max(counts.items(), key=lambda kv: (kv[1], -[r for _e, r in rows].index(kv[0])))[0]
            master = model.objects.create(organization=organization, name=best[:100])
            created += 1
        for employee, _raw in rows:
            setattr(employee, ref_field, master)
            employee.save(update_fields=[ref_field])
            linked += 1
    return created, linked


class Command(BaseCommand):
    help = "Seed permissions, default access roles and department/designation masters."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Roll back at the end.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        try:
            with transaction.atomic():
                sync_permissions()
                self.stdout.write("Permissions synced.")
                for organization in Organization.objects.order_by("id"):
                    roles = seed_organization_defaults(organization)
                    d_new, d_link = _link_text(organization, "department", "department_ref", Department)
                    g_new, g_link = _link_text(organization, "designation", "designation_ref", Designation)
                    self.stdout.write(
                        f"[{organization.id}] {organization.organization_name}: "
                        f"access roles +{len(roles)}, departments +{d_new} (linked {d_link}), "
                        f"designations +{g_new} (linked {g_link})"
                    )
                if dry:
                    raise _DryRun()
        except _DryRun:
            self.stdout.write(self.style.WARNING("Dry run: nothing saved."))
            return
        self.stdout.write(self.style.SUCCESS("Done."))
