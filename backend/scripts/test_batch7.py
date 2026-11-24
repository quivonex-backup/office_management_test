"""
Batch 7 checks: late mark deduction in payroll (settings on/off + multiplier,
late minutes from PRESENT days only, payslip LATE line, record snapshot,
calculator late_minutes).

Run after makemigrations + migrate; any database; everything is rolled back:
    python manage.py shell -c "exec(open('scripts/test_batch7.py').read())"
"""
import sys
import traceback
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.db import transaction
from rest_framework.test import APIClient

from app.accounts.models import Organization, OrganizationMembership, Role, User
from app.accounts.services import seed_organization_defaults
from app.employees.models import Employee
from app.payroll.models import (
    EmployeeSalaryAssignment, PayrollSettings, SalaryComponent, SalaryStructure, SalaryStructureComponent,
)
from app.payroll.services.attendance import classify_period
from app.payroll.services.computation import compute_payslip_data

RESULTS = []
D = Decimal
P_START, P_END = date(2026, 12, 1), date(2026, 12, 31)   # 31 days


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print(("PASS " if condition else "FAIL ") + name + ("" if condition else f"  -> {detail}"))


class Rollback(Exception):
    pass


def client_for(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def post(c, url, data=None):
    r = c.post("/" + url, data or {}, format="json")
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.content[:200]}


def attendance(late_minutes, present=31, half=0):
    """Stand-in for compute_attendance_counts (counts already classified)."""
    Z = D("0")
    return {
        "counts": {"working_days": D(present + half), "present_days": D(present), "half_days": D(half),
                   "absent_days": Z, "paid_leave_days": Z, "unpaid_leave_days": Z, "holiday_days": Z,
                   "weekly_off_days": Z, "not_employed_days": Z, "not_employed_working_days": Z},
        "overtime_minutes": 0, "late_minutes": late_minutes, "warnings": [], "notes": [],
        "requires_review": False, "sources": {},
    }


def line(data, code):
    return next((li for li in data["line_items"] if li["component_code"] == code), None)


def run():
    admin_role, _ = Role.objects.get_or_create(name="Admin", defaults={"is_active": True})
    emp_role, _ = Role.objects.get_or_create(name="Employee", defaults={"is_active": True})
    owner = User.objects.create(username="b7_owner", email="b7_owner@x.test", mobile="7000000001", role=admin_role)
    org = Organization.objects.create(organization_name="B7 Org", owner=owner, email="hr@b7.test")
    OrganizationMembership.objects.create(organization=org, user=owner, is_active=True)
    seed_organization_defaults(org)
    emp = Employee.objects.create(organization=org, first_name="Late", last_name="Comer", employee_code="B7-late",
                                  employment_status="ACTIVE")
    C = client_for(owner)

    ps = PayrollSettings.objects.create(organization=org, cycle_start_day=1, payslip_mode="SIMPLE",
                                        salary_basis="CALENDAR_DAYS", standard_work_hours_per_day=D("8"))
    check("late deduction is off by default (multiplier 1.00)",
          ps.late_deduction_enabled is False and ps.late_deduction_multiplier == D("1.00"))
    basic = SalaryComponent.objects.create(organization=org, name="Basic", code="BASIC", component_type="EARNING",
                                           calculation_type="FIXED", component_role="BASIC")
    structure = SalaryStructure.objects.create(organization=org, name="Flat", code="FLAT")
    SalaryStructureComponent.objects.create(salary_structure=structure, salary_component=basic, amount=D("31000"))
    EmployeeSalaryAssignment.objects.create(organization=org, employee=emp, salary_structure=structure,
                                            effective_from=P_START)
    # per day 31000 / 31 = 1000; per minute = 1000 / (8 x 60) = 2.0833

    # ---- attendance walk: PRESENT late counts, HALF_DAY late does not
    day_info = lambda d: {"day_type": "WORKING_DAY", "pay_type": "PAID"}
    recs = {
        date(2026, 12, 1): SimpleNamespace(status="PRESENT", overtime_minutes=0, late_minutes=30),
        date(2026, 12, 2): SimpleNamespace(status="HALF_DAY", overtime_minutes=0, late_minutes=150),
        date(2026, 12, 3): SimpleNamespace(status="PRESENT", overtime_minutes=0, late_minutes=0),
        date(2026, 12, 4): SimpleNamespace(status="PRESENT", overtime_minutes=0, late_minutes=12),
        date(2026, 12, 5): SimpleNamespace(status="ABSENT", overtime_minutes=0, late_minutes=0),
    }
    out = classify_period(date(2026, 12, 1), date(2026, 12, 5), day_info=day_info, records=recs,
                          leave_map={}, missing_action="ABSENT", today=date(2027, 1, 1))
    check("late minutes summed from PRESENT days only (30 + 12; late half day not counted)",
          out["late_minutes"] == 42, out.get("late_minutes"))

    target = "app.payroll.services.computation.compute_attendance_counts"

    with mock.patch(target, return_value=attendance(120)):
        data = compute_payslip_data(emp, org, P_START, P_END)
    check("setting off: late minutes recorded, nothing deducted",
          data["late_minutes"] == 120 and line(data, "LATE") is None and data["net"] == D("31000.00"),
          (data["late_minutes"], data["net"]))

    ps.late_deduction_enabled = True
    ps.save()
    with mock.patch(target, return_value=attendance(120)):
        data = compute_payslip_data(emp, org, P_START, P_END)
    late = line(data, "LATE")
    check("on, multiplier 1: 120 min x 2.0833 = 250.00 (LATE deduction line)",
          late and late["amount"] == D("250.00") and late["component_type"] == "DEDUCTION"
          and late["calculation_details"]["late_minutes"] == "120"
          and late["calculation_details"]["rate_per_hour"] == "125.00", late)
    check("net and totals include the late deduction",
          data["total_deductions"] == D("250.00") and data["net"] == D("30750.00")
          and data["breakdown"]["late_deduction"] == "250.00", (data["total_deductions"], data["net"]))

    ps.late_deduction_multiplier = D("2.00")
    ps.save()
    with mock.patch(target, return_value=attendance(45)):
        data = compute_payslip_data(emp, org, P_START, P_END)
    check("multiplier 2: 45 min -> 187.50", line(data, "LATE")["amount"] == D("187.50"), line(data, "LATE"))

    ps.payslip_mode = "FULL"
    ps.save()
    with mock.patch(target, return_value=attendance(45)):
        data = compute_payslip_data(emp, org, P_START, P_END)
    check("FULL payslip mode also shows the LATE line", line(data, "LATE") and line(data, "LATE")["amount"] == D("187.50"),
          [li["component_code"] for li in data["line_items"]])
    ps.payslip_mode = "SIMPLE"
    ps.save()

    with mock.patch(target, return_value=attendance(0)):
        data = compute_payslip_data(emp, org, P_START, P_END)
    check("no late minutes -> no LATE line", line(data, "LATE") is None)

    ps.late_deduction_multiplier = D("99.99")
    ps.save()
    with mock.patch(target, return_value=attendance(100000)):
        data = compute_payslip_data(emp, org, P_START, P_END)
    check("capped: net never below zero", data["net"] == D("0.00") and line(data, "LATE")["amount"] == D("31000.00")
          and line(data, "LATE")["calculation_details"]["capped_to_zero_net"] is True, (data["net"], line(data, "LATE")))
    ps.late_deduction_multiplier = D("1.00")
    ps.save()

    # ---- run: record snapshot + preview
    s, b = post(C, "payroll/settings/")
    sett = b.get("data") or {}
    check("payroll settings API returns the late fields",
          s == 200 and sett.get("late_deduction_enabled") is True and sett.get("late_deduction_multiplier") == "1.00",
          (s, sett))
    s, b = post(C, "payroll/settings/", {"late_deduction_multiplier": "-1"})
    check("negative multiplier refused", s == 400, (s, b))

    from app.payroll.models import PayrollRun
    from app.payroll.services.processing import generate_payroll
    run_obj = PayrollRun.objects.create(organization=org, period_start=P_START, period_end=P_END)
    with mock.patch(target, return_value=attendance(96)):
        generate_payroll(run_obj)
    rec = run_obj.records.get(employee=emp)
    lines = {li.component_code: li.amount for li in rec.line_items.all()}
    check("generated record stores late_minutes and the LATE line (96 min = 200.00)",
          rec.late_minutes == 96 and lines.get("LATE") == D("200.00") and rec.net == D("30800.00"),
          (rec.late_minutes, lines, rec.net))

    # ---- calculator
    body = {"period_start": str(P_START), "period_end": str(P_END), "salary_structure_id": structure.id,
            "present_days": 31, "payslip_mode": "SIMPLE"}
    s, b = post(C, "payroll/calculator/", {**body, "late_minutes": 60})
    lt = next((li for li in b.get("data", {}).get("line_items", []) if li["component_code"] == "LATE"), None)
    check("calculator takes late_minutes (60 min = 125.00) and shows the settings used",
          s == 200 and lt and lt["amount"] == "125.00"
          and b["data"]["settings_used"]["late_deduction_enabled"] is True, (s, b.get("message"), lt))
    s, b = post(C, "payroll/calculator/", {**body, "late_minutes": -5})
    s2, b2 = post(C, "payroll/calculator/", {**body, "late_minutes": "abc"})
    check("calculator rejects negative / non-number late_minutes", s == 400 and s2 == 400, (s, s2))


def main():
    try:
        with transaction.atomic():
            run()
            raise Rollback()
    except Rollback:
        pass
    except Exception:
        traceback.print_exc()
        RESULTS.append(("unexpected exception", False))

    passed = sum(1 for _, ok in RESULTS if ok)
    print(f"\n{passed}/{len(RESULTS)} checks passed. All changes rolled back.")
    if passed != len(RESULTS):
        sys.exit(1)


main()
