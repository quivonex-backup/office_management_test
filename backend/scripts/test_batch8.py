"""
Batch 8 checks: PF contribution type (STATUTORY / COMPANY_SPECIFIC / VPF),
employee vpf_percentage, payslip PDF lines in SIMPLE and FULL mode
(overtime, LOP, late deduction, late time, PF / VPF / TDS).

Run after makemigrations + migrate; any database; everything is rolled back:
    python manage.py shell -c "exec(open('scripts/test_batch8.py').read())"
"""
import sys
import traceback
from datetime import date
from decimal import Decimal
from unittest import mock

from django.db import transaction
from rest_framework.test import APIClient

from app.accounts.models import Organization, OrganizationMembership, Role, User
from app.accounts.services import seed_organization_defaults
from app.employees.models import Employee
from app.payroll.models import (
    CompanyStatutorySettings, EmployeeSalaryAssignment, PayrollRun, PayrollSettings, SalaryComponent,
    SalaryStructure, SalaryStructureComponent, StatutoryRateConfig,
)
from app.payroll.services.computation import compute_payslip_data
from app.payroll.services.processing import generate_payroll, update_payroll_record_deductions

RESULTS = []
D = Decimal
P_START, P_END = date(2026, 12, 1), date(2026, 12, 31)


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print(("PASS " if condition else "FAIL ") + name + ("" if condition else f"  -> {detail}"))


class Rollback(Exception):
    pass


def post(c, url, data=None, multipart=False):
    r = c.post("/" + url, data or {}, format="multipart" if multipart else "json")
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.content[:200]}


def attendance(late=0, ot_minutes=0, absent=0):
    Z = D("0")
    return {
        "counts": {"working_days": D(31), "present_days": D(31 - absent), "half_days": Z, "absent_days": D(absent),
                   "paid_leave_days": Z, "unpaid_leave_days": Z, "holiday_days": Z, "weekly_off_days": Z,
                   "not_employed_days": Z, "not_employed_working_days": Z},
        "overtime_minutes": ot_minutes, "late_minutes": late, "warnings": [], "notes": [],
        "requires_review": False, "sources": {},
    }


def line(data, code):
    return next((li for li in data["line_items"] if li["component_code"] == code), None)


TARGET = "app.payroll.services.computation.compute_attendance_counts"


def run():
    admin_role, _ = Role.objects.get_or_create(name="Admin", defaults={"is_active": True})
    owner = User.objects.create(username="b8_owner", email="b8_owner@x.test", mobile="8000000001", role=admin_role)
    org = Organization.objects.create(organization_name="B8 Org", owner=owner, email="hr@b8.test")
    OrganizationMembership.objects.create(organization=org, user=owner, is_active=True)
    seed_organization_defaults(org)
    C = APIClient()
    C.force_authenticate(user=owner)

    emp = Employee.objects.create(organization=org, first_name="Pf", last_name="Person", employee_code="B8-pf",
                                  employment_status="ACTIVE", pf_uan="100200300400", pan_number="ABCDE1234F")
    ps = PayrollSettings.objects.create(organization=org, cycle_start_day=1, payslip_mode="FULL",
                                        salary_basis="CALENDAR_DAYS", overtime_enabled=True,
                                        late_deduction_enabled=True)
    stat = CompanyStatutorySettings.objects.create(organization=org, is_pf_applicable=True)
    basic = SalaryComponent.objects.create(organization=org, name="Basic", code="BASIC", component_type="EARNING",
                                           calculation_type="FIXED", component_role="BASIC", is_pf_eligible=True)
    hra = SalaryComponent.objects.create(organization=org, name="HRA", code="HRA", component_type="EARNING",
                                         calculation_type="FIXED", component_role="HRA")
    structure = SalaryStructure.objects.create(organization=org, name="Std", code="STD")
    SalaryStructureComponent.objects.create(salary_structure=structure, salary_component=basic, amount=D("30000"))
    SalaryStructureComponent.objects.create(salary_structure=structure, salary_component=hra, amount=D("1000"))
    EmployeeSalaryAssignment.objects.create(organization=org, employee=emp, salary_structure=structure,
                                            effective_from=P_START)

    # standard PF rates (organization NULL) + an override for this organization (no ceiling)
    base = dict(effective_from=date(2020, 1, 1), calculation_base="PF_ELIGIBLE")
    for code, pct in (("PF_EMPLOYEE", "12"), ("PF_EMPLOYER", "3.67"), ("EPS", "8.33"), ("EDLI", "0.5")):
        StatutoryRateConfig.objects.get_or_create(organization=None, component_code=code, effective_from=base["effective_from"],
                                                  defaults={"rate_percentage": D(pct), "wage_ceiling": D("15000"),
                                                            "calculation_base": "PF_ELIGIBLE"})
    StatutoryRateConfig.objects.create(organization=org, component_code="PF_EMPLOYEE", rate_percentage=D("12"),
                                       wage_ceiling=None, **base)

    s, b = post(C, "payroll/statutory-settings/")
    info = b.get("data", {}).get("pf_rate_info", {})
    check("statutory settings show pf_rate_info (STATUTORY -> standard)",
          s == 200 and info.get("rates_used") == "STANDARD" and info.get("company_rate_configs") == 1, (s, info))

    with mock.patch(TARGET, return_value=attendance()):
        data = compute_payslip_data(emp, org, P_START, P_END)
    std_pf = StatutoryRateConfig.objects.filter(organization=None, component_code="PF_EMPLOYEE").first()
    expected_std = (min(D("30000"), std_pf.wage_ceiling) * std_pf.rate_percentage / 100).quantize(D("0.01")) \
        if std_pf.wage_ceiling else (D("30000") * std_pf.rate_percentage / 100).quantize(D("0.01"))
    check("STATUTORY: standard rate, organization override ignored",
          data["pf_employee"] == expected_std and line(data, "VPF") is None, (data["pf_employee"], expected_std))

    s, b = post(C, "payroll/statutory-settings/", {"pf_contribution_type": "COMPANY_SPECIFIC"})
    check("COMPANY_SPECIFIC with an override -> rates_used COMPANY",
          s == 200 and b["data"]["pf_rate_info"]["rates_used"] == "COMPANY", (s, b.get("data", {}).get("pf_rate_info")))
    stat.refresh_from_db()
    with mock.patch(TARGET, return_value=attendance()):
        data = compute_payslip_data(emp, org, P_START, P_END)
    check("COMPANY_SPECIFIC: organization rate used (12% of full 30000 = 3600)",
          data["pf_employee"] == D("3600.00"), data["pf_employee"])

    # ---- VPF
    s, b = post(C, "employees/update/", {"employee_id": emp.id, "vpf_percentage": "90"}, multipart=True)
    check("employee vpf_percentage above 88 -> 400", s == 400, (s, b))
    s, b = post(C, "employees/update/", {"employee_id": emp.id, "vpf_percentage": "10"}, multipart=True)
    emp.refresh_from_db()
    check("employees/update sets vpf_percentage", s == 200 and emp.vpf_percentage == D("10.00"), (s, b.get("message")))
    s, b = post(C, "employees/detail/", {"employee_id": emp.id})
    check("vpf_percentage in employee detail", s == 200 and b["data"].get("vpf_percentage") == "10.00",
          b.get("data", {}).get("vpf_percentage"))

    with mock.patch(TARGET, return_value=attendance()):
        data = compute_payslip_data(emp, org, P_START, P_END)
    check("VPF % ignored unless the contribution type is VPF", line(data, "VPF") is None and data["vpf_employee"] == 0)

    post(C, "payroll/statutory-settings/", {"pf_contribution_type": "VPF"})
    with mock.patch(TARGET, return_value=attendance()):
        data = compute_payslip_data(emp, org, P_START, P_END)
    vpf = line(data, "VPF")
    pf_wage = D(vpf["calculation_details"]["pf_wage"]) if vpf else None
    check("VPF: standard PF + VPF line (10% of the PF wage), employer share unchanged",
          vpf and vpf["amount"] == (pf_wage * D("0.10")).quantize(D("0.01")) and data["pf_employee"] == expected_std
          and data["vpf_employee"] == vpf["amount"], (vpf, data["pf_employee"]))
    check("VPF counted in total deductions", data["total_deductions"] == data["pf_employee"] + data["vpf_employee"],
          (data["total_deductions"], data["pf_employee"], data["vpf_employee"]))
    s, b = post(C, "payroll/statutory-settings/")
    check("pf_rate_info for VPF counts employees with a VPF %",
          b["data"]["pf_rate_info"]["vpf_employees"] == 1, b["data"]["pf_rate_info"])

    s, b = post(C, "payroll/calculator/", {"period_start": str(P_START), "period_end": str(P_END),
                                            "employee_id": emp.id, "present_days": 31, "payslip_mode": "FULL"})
    lines = {li["component_code"]: li["amount"] for li in b.get("data", {}).get("line_items", [])}
    check("calculator FULL shows PF + VPF", s == 200 and "PF" in lines and "VPF" in lines, (s, b.get("message"), lines))

    # ---- generated record + payslip PDF (FULL)
    run_obj = PayrollRun.objects.create(organization=org, period_start=P_START, period_end=P_END)
    with mock.patch(TARGET, return_value=attendance(late=80, ot_minutes=120, absent=1)):
        generate_payroll(run_obj)
    rec = run_obj.records.get(employee=emp)
    check("record stores vpf_employee + late_minutes", rec.vpf_employee > 0 and rec.late_minutes == 80,
          (rec.vpf_employee, rec.late_minutes))
    update_payroll_record_deductions(rec, tds=D("500"), updated_by=owner)
    rec.refresh_from_db()

    from app.payroll.services import payslip as payslip_service
    captured = {}
    real_render = payslip_service.render_to_string

    def capture(name, context):
        html = real_render(name, context)
        captured["html"] = html
        return html

    with mock.patch.object(payslip_service, "render_to_string", side_effect=capture):
        pdf = payslip_service.generate_payslip_pdf(rec)
    html = captured.get("html", "")
    check("FULL payslip PDF: components, OT, PF, VPF, TDS, LOP, late, late time",
          pdf[:4] == b"%PDF" and all(t in html for t in (
              "Basic", "Overtime", "Provident Fund (Employee)", "Voluntary PF (Employee)", "TDS",
              "Loss of Pay", "Late Deduction", "Late Time", "1 h 20 min", "PF Employer Contribution")),
          [t for t in ("Basic", "Overtime", "Provident Fund (Employee)", "Voluntary PF (Employee)", "TDS",
                       "Loss of Pay", "Late Deduction", "Late Time", "1 h 20 min") if t not in html])

    # ---- SIMPLE mode payslip PDF
    ps.payslip_mode = "SIMPLE"
    ps.save()
    run2 = PayrollRun.objects.create(organization=org, period_start=date(2027, 1, 1), period_end=date(2027, 1, 31))
    EmployeeSalaryAssignment.objects.filter(employee=emp).update(effective_from=P_START)
    with mock.patch(TARGET, return_value=attendance(late=45, ot_minutes=60, absent=1)):
        generate_payroll(run2)
    rec2 = run2.records.get(employee=emp)
    with mock.patch.object(payslip_service, "render_to_string", side_effect=capture):
        payslip_service.generate_payslip_pdf(rec2)
    html = captured.get("html", "")
    check("SIMPLE payslip PDF lists Gross Salary, Overtime, Loss of Pay, Late Deduction (not only totals)",
          all(t in html for t in ("Gross Salary", "Overtime", "Loss of Pay", "Late Deduction", "45 min",
                                  "Total Deductions")),
          [t for t in ("Gross Salary", "Overtime", "Loss of Pay", "Late Deduction", "45 min") if t not in html])
    check("SIMPLE payslip PDF has no statutory / employer section",
          "Provident Fund" not in html and "PF Employer Contribution" not in html)


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
