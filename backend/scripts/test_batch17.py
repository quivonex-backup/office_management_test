"""
Batch 17 checks: salary assignment package (annual_ctc / monthly_gross) is
never saved empty: auto-filled from a fixed structure, required for a
gross-based structure; backfill_salary_packages command.

Run after migrate; any database; everything is rolled back:
    python manage.py shell -c "exec(open('scripts/test_batch17.py').read())"
"""
import io
import sys
import traceback
from datetime import date
from decimal import Decimal

from django.core.management import call_command
from django.db import transaction
from rest_framework.test import APIClient

from app.accounts.models import Organization, OrganizationMembership, Role, User
from app.accounts.services import seed_organization_defaults
from app.employees.models import Employee
from app.payroll.models import (
    EmployeeSalaryAssignment, PayrollSettings, SalaryComponent, SalaryStructure, SalaryStructureComponent,
)
from app.payroll.services import compute_ctc_breakup

RESULTS = []
D = Decimal


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print(("PASS " if condition else "FAIL ") + name + ("" if condition else f"  -> {detail}"))


class Rollback(Exception):
    pass


def post(c, url, data=None):
    r = c.post("/" + url, data or {}, format="json")
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.content[:200]}


def run():
    admin_role, _ = Role.objects.get_or_create(name="Admin", defaults={"is_active": True})
    emp_role, _ = Role.objects.get_or_create(name="Employee", defaults={"is_active": True})
    n = [0]

    def user(name, role=emp_role):
        n[0] += 1
        return User.objects.create(username=f"b17_{name}", email=f"b17_{name}@x.test", mobile=f"17000000{n[0]:02d}",
                                   role=role, first_name=name.title())

    owner = user("owner", admin_role)
    org = Organization.objects.create(organization_name="B17 Org", owner=owner)
    OrganizationMembership.objects.create(organization=org, user=owner, is_active=True)
    seed_organization_defaults(org)
    C = APIClient()
    C.force_authenticate(user=owner)

    def employee(name):
        u = user(name)
        OrganizationMembership.objects.create(organization=org, user=u, is_active=True)
        return Employee.objects.create(organization=org, first_name=name.title(), last_name="T",
                                       employee_code=f"B17-{name}", user=u, employment_status="ACTIVE",
                                       joining_date=date(2025, 1, 1))

    e1, e2, e3, e4, e5 = (employee(x) for x in ("e1", "e2", "e3", "e4", "e5"))
    settings = PayrollSettings.objects.create(organization=org, cycle_start_day=1, payslip_mode="SIMPLE",
                                              salary_basis="CALENDAR_DAYS", standard_work_hours_per_day=D("8"))

    def comp(code, **kw):
        return SalaryComponent.objects.create(organization=org, name=code.title(), code=code,
                                              component_type=kw.pop("component_type", "EARNING"), **kw)

    basic = comp("B17BASIC", component_role="BASIC")
    hra = comp("B17HRA", calculation_type="PERCENTAGE", percentage_of_component=basic)
    special = comp("B17SPL")
    bal = comp("B17BAL")
    pct_gross = comp("B17PG", calculation_type="PERCENTAGE")

    fixed = SalaryStructure.objects.create(organization=org, name="Fixed", code="B17FIX")
    SalaryStructureComponent.objects.create(salary_structure=fixed, salary_component=basic, amount=D("20000"))
    SalaryStructureComponent.objects.create(salary_structure=fixed, salary_component=hra, percentage=D("40"))
    SalaryStructureComponent.objects.create(salary_structure=fixed, salary_component=special, amount=D("5000"))

    fixed2 = SalaryStructure.objects.create(organization=org, name="Fixed Two", code="B17FX2")
    SalaryStructureComponent.objects.create(salary_structure=fixed2, salary_component=basic, amount=D("10000"))

    gross_based = SalaryStructure.objects.create(organization=org, name="Gross Based", code="B17GB")
    SalaryStructureComponent.objects.create(salary_structure=gross_based, salary_component=pct_gross, percentage=D("50"))
    SalaryStructureComponent.objects.create(salary_structure=gross_based, salary_component=bal, is_balancing=True)

    balancing_only = SalaryStructure.objects.create(organization=org, name="Balancing", code="B17BO")
    SalaryStructureComponent.objects.create(salary_structure=balancing_only, salary_component=basic, amount=D("10000"))
    SalaryStructureComponent.objects.create(salary_structure=balancing_only, salary_component=bal, is_balancing=True)

    empty = SalaryStructure.objects.create(organization=org, name="Empty", code="B17EMP")
    SalaryStructureComponent.objects.create(salary_structure=empty, salary_component=special, amount=D("0"))

    start = "2026-11-01"

    # ================= CREATE
    s, b = post(C, "payroll/assignments/create/", {"employee": e1.id, "salary_structure": fixed.id,
                                                  "effective_from": start})
    d = b.get("data") or {}
    check("create without package -> auto-filled gross 33000 / CTC 396000 (SIMPLE)",
          s == 201 and D(d["monthly_gross"]) == D("33000") and D(d["annual_ctc"]) == D("396000"), b)
    expected = compute_ctc_breakup(org, fixed, None, as_of=date(2026, 11, 1))
    check("same numbers as compute_ctc_breakup (calculator)",
          D(d["monthly_gross"]) == expected["monthly_gross"] and D(d["annual_ctc"]) == expected["annual_ctc"])

    s, b = post(C, "payroll/assignments/create/", {"employee": e2.id, "salary_structure": gross_based.id,
                                                  "effective_from": start})
    check("gross-based structure without package -> 400 annual_ctc",
          s == 400 and "annual_ctc" in str(b.get("errors")) and "Gross Based" in str(b), b)
    s, b = post(C, "payroll/assignments/create/", {"employee": e2.id, "salary_structure": balancing_only.id,
                                                  "effective_from": start})
    check("balancing component -> 400", s == 400, b)
    s, b = post(C, "payroll/assignments/create/", {"employee": e2.id, "salary_structure": empty.id,
                                                  "effective_from": start})
    check("structure with zero salary -> 400", s == 400 and "no salary" in str(b), b)
    s, b = post(C, "payroll/assignments/create/", {"employee": e2.id, "salary_structure": gross_based.id,
                                                  "effective_from": start, "monthly_gross": "40000"})
    check("gross-based with monthly_gross -> 201, CTC worked out",
          s == 201 and D(b["data"]["monthly_gross"]) == D("40000") and D(b["data"]["annual_ctc"]) == D("480000"), b)
    s, b = post(C, "payroll/assignments/create/", {"employee": e3.id, "salary_structure": fixed.id,
                                                  "effective_from": start, "annual_ctc": "600000",
                                                  "monthly_gross": "50000"})
    check("both sent -> stored as sent", s == 201 and D(b["data"]["annual_ctc"]) == D("600000")
          and D(b["data"]["monthly_gross"]) == D("50000"), b)
    a3 = b["data"]["id"]
    s, b = post(C, "payroll/assignments/create/", {"employee": e4.id, "salary_structure": fixed.id,
                                                  "effective_from": start, "annual_ctc": None, "monthly_gross": None})
    check("both null on create -> auto-filled", s == 201 and D(b["data"]["monthly_gross"]) == D("33000"), b)
    a4 = b["data"]["id"]

    # ================= UPDATE
    s, b = post(C, "payroll/assignments/update/", {"assignment_id": a3, "reason": "typo fix"})
    check("update reason only -> package kept", s == 200 and D(b["data"]["annual_ctc"]) == D("600000"), b)
    s, b = post(C, "payroll/assignments/update/", {"assignment_id": a3, "salary_structure": fixed2.id})
    check("update structure, no package -> refilled from new structure (10000 / 120000)",
          s == 200 and D(b["data"]["monthly_gross"]) == D("10000") and D(b["data"]["annual_ctc"]) == D("120000"), b)
    s, b = post(C, "payroll/assignments/update/", {"assignment_id": a3, "salary_structure": gross_based.id})
    check("update to gross-based structure, no package -> 400", s == 400, b)
    s, b = post(C, "payroll/assignments/update/", {"assignment_id": a3, "salary_structure": gross_based.id,
                                                  "annual_ctc": "360000"})
    check("update to gross-based with annual_ctc -> 200", s == 200 and D(b["data"]["annual_ctc"]) == D("360000")
          and D(b["data"]["monthly_gross"]) == D("30000"), b)
    s, b = post(C, "payroll/assignments/update/", {"assignment_id": a3, "annual_ctc": None, "monthly_gross": None})
    check("clear both on gross-based -> 400 (cannot be empty)", s == 400, b)
    s, b = post(C, "payroll/assignments/update/", {"assignment_id": a4, "annual_ctc": None, "monthly_gross": None})
    check("clear both on fixed -> back to structure package", s == 200 and D(b["data"]["monthly_gross"]) == D("33000"), b)
    s, b = post(C, "payroll/assignments/update/", {"assignment_id": a4, "monthly_gross": "0"})
    check("zero -> 400 (unchanged rule)", s == 400, b)

    # ================= BULK ASSIGN
    s, b = post(C, "payroll/assignments/bulk-assign/", {"employee_ids": [e5.id], "salary_structure_id": gross_based.id,
                                                       "effective_from": start})
    check("bulk-assign gross-based without package -> 400", s == 400 and "Gross Based" in b["message"], b)
    s, b = post(C, "payroll/assignments/bulk-assign/", {"employee_ids": [e5.id], "salary_structure_id": fixed.id,
                                                       "effective_from": start})
    a5 = EmployeeSalaryAssignment.objects.filter(employee=e5).first()
    check("bulk-assign fixed without package -> filled", s in (200, 201) and a5 and a5.monthly_gross == D("33000")
          and a5.annual_ctc == D("396000"), b)

    # ================= NO PAYROLL SETTINGS -> 12 x gross
    settings_id = settings.id
    PayrollSettings.objects.filter(pk=settings_id).delete()
    from app.payroll.services import default_package_from_structure
    pkg = default_package_from_structure(org, fixed, as_of=date(2026, 11, 1))
    check("no payroll settings -> gross 33000, CTC 12 x gross", pkg["monthly_gross"] == D("33000")
          and pkg["annual_ctc"] == D("396000"), pkg)
    PayrollSettings.objects.create(organization=org, cycle_start_day=1, payslip_mode="SIMPLE",
                                   salary_basis="CALENDAR_DAYS", standard_work_hours_per_day=D("8"))

    # ================= BACKFILL COMMAND
    old_fixed = EmployeeSalaryAssignment.objects.create(organization=org, employee=e1, salary_structure=fixed2,
                                                        effective_from=date(2025, 1, 1), effective_to=date(2025, 12, 31))
    old_gross = EmployeeSalaryAssignment.objects.create(organization=org, employee=e2, salary_structure=gross_based,
                                                        effective_from=date(2025, 1, 1), effective_to=date(2025, 12, 31))
    out = io.StringIO()
    call_command("backfill_salary_packages", "--dry-run", "--organization", str(org.id), stdout=out)
    old_fixed.refresh_from_db()
    text = out.getvalue()
    check("backfill dry run: lists, saves nothing", "WOULD FILL" in text and "NEEDS HR" in text
          and old_fixed.monthly_gross is None, text)
    out = io.StringIO()
    call_command("backfill_salary_packages", "--organization", str(org.id), stdout=out)
    old_fixed.refresh_from_db()
    old_gross.refresh_from_db()
    check("backfill: fixed filled, gross-based left for HR",
          old_fixed.monthly_gross == D("10000") and old_fixed.annual_ctc == D("120000")
          and old_gross.monthly_gross is None and "1 need a CTC" in out.getvalue(), out.getvalue())


try:
    with transaction.atomic():
        run()
        raise Rollback()
except Rollback:
    pass
except Exception:
    traceback.print_exc()
    RESULTS.append(("crashed", False))

passed = sum(1 for _, ok in RESULTS if ok)
print(f"\nBatch 17: {passed}/{len(RESULTS)} passed (all changes rolled back)")
if passed != len(RESULTS):
    sys.exit(1)
