"""
Batch 3 checks: CTC / monthly gross in payroll, and the recruitment flow
Applicant -> Verification -> Onboarding -> Employee.

Run after makemigrations + migrate (+ seed_org_access); any database;
everything is rolled back at the end:
    python manage.py shell -c "exec(open('scripts/test_batch3.py').read())"
"""
import sys
import traceback
from datetime import date
from decimal import Decimal
from unittest import mock

from django.db import transaction
from django.test.utils import override_settings
from rest_framework.test import APIClient

from app.accounts.models import AccessRole, Branch, Organization, OrganizationMembership, Role, User
from app.accounts.services import seed_organization_defaults
from app.employees.models import Department, Designation, Employee, EmployeeDocument
from app.leave.models import EmployeeLeaveBalance, LeaveType
from app.payroll.models import (
    CompanyStatutorySettings, EmployeeSalaryAssignment, PayrollSettings, SalaryComponent,
    SalaryStructure, SalaryStructureComponent, StatutoryRateConfig,
)
from app.payroll.services import compute_ctc_breakup, compute_payslip_data, monthly_gross_from_annual_ctc
from app.payroll.services.computation import _resolve_component_amounts
from app.recruitment.models import Applicant, ApplicantOffer

RESULTS = []
D = Decimal


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print(("PASS " if condition else "FAIL ") + name + ("" if condition else f"  -> {detail}"))


class Rollback(Exception):
    pass


def client_for(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def post(c, url, data=None, multipart=False):
    r = c.post("/" + url, data or {}, format="multipart" if multipart else "json")
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.content[:300]}
    return r.status_code, body


def run():
    admin_role, _ = Role.objects.get_or_create(name="Admin", defaults={"is_active": True})
    emp_role, _ = Role.objects.get_or_create(name="Employee", defaults={"is_active": True})
    n = [0]

    def user(name, role=emp_role):
        n[0] += 1
        u = User.objects.create(username=f"b3_{name}", email=f"b3_{name}@x.test", mobile=f"70000000{n[0]:02d}", role=role)
        u.set_password("x-test-123")
        u.save()
        return u

    owner = user("owner", admin_role)
    org = Organization.objects.create(organization_name="B3 Org", owner=owner)
    OrganizationMembership.objects.create(organization=org, user=owner, is_active=True)
    seed_organization_defaults(org)
    roles = {r.name: r for r in AccessRole.objects.filter(organization=org)}

    def employee(name, role_name=None, manager=None):
        u = user(name)
        OrganizationMembership.objects.create(organization=org, user=u, is_active=True)
        return Employee.objects.create(organization=org, first_name=name.title(), last_name="T",
                                       employee_code=f"B3-{name}", user=u, access_role=roles.get(role_name),
                                       reports_to=manager, employment_status="ACTIVE", pf_uan="100000000001",
                                       pan_number="ABCDE1234A", esi_ip_number="1234567890")

    hr = employee("hr", "HR Manager")
    hrx = employee("hrx", "HR Executive")
    mgr = employee("mgr", "Department Manager")
    plain = employee("plain")
    C = {k: client_for(v.user) for k, v in dict(hr=hr, hrx=hrx, mgr=mgr, plain=plain).items()}
    C["owner"] = client_for(owner)

    # ---------------- payroll setup
    PayrollSettings.objects.create(organization=org, cycle_start_day=1, payslip_mode="FULL")
    CompanyStatutorySettings.objects.create(organization=org, is_pf_applicable=True, is_esi_applicable=True)
    for code, rate, ceiling, base in (("PF_EMPLOYEE", "12", "15000", "PF_ELIGIBLE"), ("PF_EMPLOYER", "12", "15000", "PF_ELIGIBLE"),
                                      ("EPS", "8.33", "15000", "PF_ELIGIBLE"), ("EDLI", "0.5", "15000", "PF_ELIGIBLE"),
                                      ("ESI_EMPLOYEE", "0.75", "21000", "ESI_ELIGIBLE"), ("ESI_EMPLOYER", "3.25", "21000", "ESI_ELIGIBLE")):
        StatutoryRateConfig.objects.create(organization=org, component_code=code, rate_percentage=D(rate),
                                           wage_ceiling=D(ceiling), calculation_base=base, effective_from=date(2014, 1, 1))

    def comp(code, ctype="EARNING", calc="FIXED", role="ALLOWANCE", base=None, pf=False, esi=True):
        return SalaryComponent.objects.create(organization=org, name=code.title(), code=code, component_type=ctype,
                                              calculation_type=calc, component_role=role, percentage_of_component=base,
                                              is_pf_eligible=pf, is_esi_eligible=esi)

    basic = comp("BASIC", calc="PERCENTAGE", role="BASIC", pf=True)
    hra = comp("HRA", calc="PERCENTAGE", role="HRA", base=basic)
    conv = comp("CONV")
    special = comp("SPECIAL")
    loan = comp("LOAN", ctype="DEDUCTION", esi=False)

    dev = SalaryStructure.objects.create(organization=org, name="Developer", code="DEV")
    SalaryStructureComponent.objects.create(salary_structure=dev, salary_component=basic, percentage=D("50"))
    SalaryStructureComponent.objects.create(salary_structure=dev, salary_component=hra, percentage=D("40"))
    SalaryStructureComponent.objects.create(salary_structure=dev, salary_component=conv, amount=D("1600"))
    SalaryStructureComponent.objects.create(salary_structure=dev, salary_component=special, amount=D("0"), is_balancing=True)

    legacy = SalaryStructure.objects.create(organization=org, name="Legacy", code="LEG")
    lbasic = comp("LBASIC", role="BASIC", pf=True)
    SalaryStructureComponent.objects.create(salary_structure=legacy, salary_component=lbasic, amount=D("20000"))
    lhra = comp("LHRA", calc="PERCENTAGE", role="HRA", base=lbasic)
    SalaryStructureComponent.objects.create(salary_structure=legacy, salary_component=lhra, percentage=D("40"))

    # ================= CTC maths
    amounts, _ = _resolve_component_amounts(dev, monthly_gross=D("50000"))
    check("gross 50000: Basic 50% / HRA 40% of Basic / Conv fixed / Special = balance",
          (amounts["BASIC"], amounts["HRA"], amounts["CONV"], amounts["SPECIAL"]) == (D("25000.00"), D("10000.00"), D("1600.00"), D("13400.00")), amounts)
    amounts, _ = _resolve_component_amounts(legacy)
    check("legacy structure without gross unchanged", (amounts["LBASIC"], amounts["LHRA"]) == (D("20000.00"), D("8000.00")), amounts)
    amounts, _ = _resolve_component_amounts(dev)
    check("structure without gross: % of gross components stay 0 (old behaviour)", amounts["BASIC"] == 0 and amounts["SPECIAL"] == 0, amounts)

    b = compute_ctc_breakup(org, dev, D("50000"), as_of=date(2026, 12, 1))
    check("CTC: PF employer 12% of 15000 ceiling + EDLI 0.5%, ESI 0 above ceiling",
          b["employer_contributions"]["pf_employer"] == D("1800.00") and b["employer_contributions"]["edli"] == D("75.00")
          and b["employer_contributions"]["esi_employer"] == 0, b["employer_contributions"])
    check("CTC: annual = 12 x (gross + employer cost) = 622500", b["annual_ctc"] == D("622500.00"), b["annual_ctc"])
    r = monthly_gross_from_annual_ctc(org, dev, D("622500"), as_of=date(2026, 12, 1))
    check("CTC -> gross solves back to 50000", r["monthly_gross"] == D("50000.00") and r["difference"] == 0, (r["monthly_gross"], r["difference"]))
    b = compute_ctc_breakup(org, dev, D("18000"), as_of=date(2026, 12, 1))
    check("CTC below ESI ceiling includes ESI employer 3.25%", b["employer_contributions"]["esi_employer"] == D("585.00"), b["employer_contributions"])
    ps = PayrollSettings.objects.get(organization=org)
    ps.ctc_includes_employer_contributions = False
    ps.save()
    check("CTC setting off: annual = 12 x gross", compute_ctc_breakup(org, dev, D("50000"))["annual_ctc"] == D("600000.00"))
    ps.ctc_includes_employer_contributions = True
    ps.save()

    # ================= payroll API
    s, body = post(C["hr"], "payroll/assignments/create/", {"employee": plain.id, "salary_structure": dev.id,
                                                            "effective_from": "2026-12-01", "annual_ctc": "622500"})
    check("assignments/create with annual_ctc fills monthly_gross", s == 201 and body["data"]["monthly_gross"] == "50000.00", (s, body))
    a = EmployeeSalaryAssignment.objects.get(employee=plain)
    data = compute_payslip_data(plain, org, date(2026, 12, 1), date(2026, 12, 31))
    check("payroll run uses the assignment gross (monthly_salary 50000, Basic 25000)",
          data["monthly_salary"] == D("50000.00") and data["breakdown"]["component_amounts"]["BASIC"] == "25000.00",
          (data["monthly_salary"], data["breakdown"]["component_amounts"]))
    check("payroll: no package warning when the structure matches", not any("agreed monthly gross" in w for w in data["warnings"]), data["warnings"])
    a.salary_structure = legacy
    a.save()
    data = compute_payslip_data(plain, org, date(2026, 12, 1), date(2026, 12, 31))
    check("payroll: warning when the structure cannot reach the agreed gross",
          any("agreed monthly gross" in w for w in data["warnings"]) and data["requires_review"], data["warnings"])
    a.delete()

    s, body = post(C["hr"], "payroll/calculator/", {"period_start": "2026-12-01", "period_end": "2026-12-31",
                                                    "salary_structure_id": dev.id, "monthly_gross": "50000",
                                                    "present_days": 31, "payslip_mode": "SIMPLE"})
    check("calculator with monthly_gross returns ctc_breakup",
          s == 200 and body["data"]["ctc_breakup"]["monthly_gross"] == "50000.00", (s, body.get("message"), body.get("data", {}).get("ctc_breakup")))
    s, body = post(C["owner"], "payroll/structures/create/", {"name": "Bad", "code": "BAD", "components": [
        {"salary_component": conv.id, "amount": "100", "is_balancing": True},
        {"salary_component": special.id, "amount": "0", "is_balancing": True}]})
    check("structure with two balancing components -> 400", s == 400, (s, body))
    s, body = post(C["owner"], "payroll/structures/create/", {"name": "Bad2", "code": "BAD2", "components": [
        {"salary_component": loan.id, "is_balancing": True}]})
    check("balancing on a deduction -> 400", s == 400, (s, body))
    s, body = post(C["owner"], "payroll/structures/create/", {"name": "Ok", "code": "OK1", "components": [
        {"salary_component": basic.id, "percentage": "40"}, {"salary_component": special.id, "is_balancing": True}]})
    check("structure with one balancing component -> 201 and is_balancing returned",
          s == 201 and any(c.get("is_balancing") for c in body["data"].get("components", [])), (s, body))

    # ================= recruitment
    dept = Department.objects.create(organization=org, name="Engineering")
    desig = Designation.objects.create(organization=org, name="Python Developer")
    pune = Branch.objects.create(organization=org, name="Pune")
    LeaveType.objects.create(organization=org, name="Casual", code="CL", annual_allocation=12)
    payload = {
        "first_name": "Rahul", "last_name": "Patil", "email": "Rahul.Patil@x.test", "mobile": "9876500001",
        "designation_id": desig.id, "department_id": dept.id, "branch_id": pune.id, "source": "REFERRAL",
        "referred_by_id": mgr.id, "total_experience_years": "3.5", "expected_ctc": "700000",
        "education": [{"degree": "B.E.", "institution": "COEP", "year": 2021}],
        "experience": [{"company": "Acme", "designation": "Dev", "from_date": "2021-07-01", "to_date": "2024-06-30"}],
    }
    s, body = post(C["plain"], "recruitment/applicant/create/", payload)
    check("applicant/create without applicant.create -> 403", s == 403, s)
    with mock.patch("app.recruitment.views.upload_to_s3", return_value="recruitment/documents/stub.pdf"):
        from django.core.files.uploadedfile import SimpleUploadedFile
        mp = {k: (v if not isinstance(v, list) else __import__("json").dumps(v)) for k, v in payload.items()}
        mp["resume"] = SimpleUploadedFile("cv.pdf", b"%PDF-1.4", content_type="application/pdf")
        s, body = post(C["hrx"], "recruitment/applicant/create/", mp, multipart=True)
    ok = s == 201
    check("applicant/create by HR Executive (multipart, JSON lists, resume) -> 201", ok, (s, body))
    if not ok:
        return
    d = body["data"]
    aid = d["applicant"]["id"]
    check("new applicant: code, APPLICANT/PENDING, email lower-cased, resume stored, history CREATED",
          d["applicant"]["applicant_code"].startswith("APL-") and d["applicant"]["stage"] == "APPLICANT"
          and d["applicant"]["status"] == "PENDING" and d["applicant"]["email"] == "rahul.patil@x.test"
          and d["documents"][0]["document_type"] == "RESUME" and d["history"][0]["action"] == "CREATED"
          and d["applicant"]["education"][0]["degree"] == "B.E.", d)
    s, body = post(C["hrx"], "recruitment/applicant/create/", {**payload, "mobile": "9000011111"})
    check("duplicate open applicant (same email) -> 400", s == 400 and "already exists" in body["message"], (s, body))

    s, body = post(C["mgr"], "recruitment/applicant/list/")
    check("view-only manager sees no unassigned applicants", s == 200 and body["data"] == [], (s, body))
    s, body = post(C["hrx"], "recruitment/applicant/update/", {"applicant_id": aid, "interviews": [
        {"round_name": "Technical", "scheduled_at": "2026-11-25T11:00:00+05:30", "interviewer_id": mgr.id, "mode": "VIDEO"},
        {"round_name": "HR", "interviewer_id": hr.id}]})
    check("HR adds two interviews via applicant/update", s == 200 and len(body["data"]["interviews"]) == 2, (s, body))
    tech_id = next(i["id"] for i in body["data"]["interviews"] if i["round_name"] == "Technical")
    hr_round_id = next(i["id"] for i in body["data"]["interviews"] if i["round_name"] == "HR")
    s, body = post(C["mgr"], "recruitment/applicant/list/")
    check("interviewer now sees the applicant", s == 200 and [r["id"] for r in body["data"]] == [aid], (s, body))
    s, body = post(C["mgr"], "recruitment/applicant/update/", {"applicant_id": aid, "interviews": [
        {"id": tech_id, "result": "PASSED", "rating": 4, "feedback": "Strong Python", "round_name": "Hacked"}]})
    tech = next((i for i in body.get("data", {}).get("interviews", []) if i["id"] == tech_id), {})
    check("interviewer records feedback; cannot rename the round",
          s == 200 and tech.get("result") == "PASSED" and tech.get("round_name") == "Technical", (s, body))
    s, _ = post(C["mgr"], "recruitment/applicant/update/", {"applicant_id": aid, "first_name": "X"})
    check("interviewer cannot edit applicant fields -> 403", s == 403, s)
    s, _ = post(C["mgr"], "recruitment/applicant/update/", {"applicant_id": aid, "interviews": [{"id": hr_round_id, "result": "PASSED"}]})
    check("interviewer cannot touch someone else's interview -> 403", s == 403, s)
    s, body = post(C["hrx"], "recruitment/applicant/list/", {"search": "rahul"})
    check("list summary counts", s == 200 and body["summary"]["total"] == 1 and body["summary"]["by_stage"]["APPLICANT"] == 1, body.get("summary"))

    # ---- status
    s, _ = post(C["mgr"], "recruitment/applicant/status-update/", {"applicant_id": aid, "status": "SELECTED"})
    check("status-update without permission -> 403", s == 403, s)
    s, body = post(C["hrx"], "recruitment/applicant/status-update/", {"applicant_id": aid, "status": "SHORTLISTED"})
    check("PENDING -> SHORTLISTED", s == 200 and body["data"]["applicant"]["status"] == "SHORTLISTED", (s, body))
    s, body = post(C["hrx"], "recruitment/applicant/status-update/", {"applicant_id": aid, "status": "SELECTED", "note": "Cleared rounds"})
    check("SELECTED moves to VERIFICATION with 6 checks and primary action 'verification'",
          s == 200 and body["data"]["applicant"]["stage"] == "VERIFICATION" and len(body["data"]["verification_checks"]) == 6
          and body["data"]["primary_action"] == "verification", (s, body))
    s, body = post(C["hrx"], "recruitment/applicant/status-update/", {"applicant_id": aid, "status": "SHORTLISTED"})
    check("invalid move in VERIFICATION -> 400", s == 400, (s, body))

    # ---- verification + offer
    s, body = post(C["hrx"], "recruitment/applicant/verification/", {"applicant_id": aid, "offer": {
        "salary_structure_id": dev.id, "joining_date": "2026-12-10", "annual_ctc": "622500"}})
    off = body.get("data", {}).get("current_offer") or {}
    check("offer v1 from annual CTC: gross 50000, breakup stored, SALARY_OFFER done",
          s == 200 and off.get("version") == 1 and off.get("monthly_gross") == "50000.00" and off.get("breakup", {}).get("annual_ctc") == "622500.00"
          and next(c for c in body["data"]["verification_checks"] if c["key"] == "SALARY_OFFER")["status"] == "DONE", (s, body))
    s, body = post(C["hrx"], "recruitment/applicant/verification/", {"applicant_id": aid, "complete": True})
    check("complete before acceptance -> 400", s == 400 and "accepted" in body["message"], (s, body))
    s, body = post(C["hrx"], "recruitment/applicant/verification/", {"applicant_id": aid, "offer": {
        "salary_structure_id": dev.id, "joining_date": "2026-12-10", "monthly_gross": "52000", "notes": "Revised"}})
    statuses = {o["version"]: o["status"] for o in body.get("data", {}).get("offers", [])}
    check("revised offer: v1 SUPERSEDED, v2 DRAFT with CTC worked out", s == 200 and statuses == {1: "SUPERSEDED", 2: "DRAFT"}
          and body["data"]["current_offer"]["annual_ctc"] == "646500.00", (s, statuses, body.get("data", {}).get("current_offer")))
    o1 = ApplicantOffer.objects.get(applicant_id=aid, version=1)
    o1.annual_ctc = D("1")
    try:
        o1.save()
        check("offer terms are immutable", False, "saved")
    except ValueError:
        check("offer terms are immutable", True)
    s, body = post(C["hrx"], "recruitment/applicant/verification/", {"applicant_id": aid, "checks": [{"key": "OFFER_ACCEPTANCE", "status": "DONE"}]})
    check("system check cannot be set by hand -> 400", s == 400, (s, body))
    s, body = post(C["hrx"], "recruitment/applicant/verification/", {"applicant_id": aid, "offer_action": "SEND"})
    s, body = post(C["hrx"], "recruitment/applicant/verification/", {"applicant_id": aid, "offer_action": "ACCEPT"})
    check("offer SENT -> ACCEPTED marks OFFER_ACCEPTANCE done",
          s == 200 and body["data"]["current_offer"]["status"] == "ACCEPTED"
          and next(c for c in body["data"]["verification_checks"] if c["key"] == "OFFER_ACCEPTANCE")["status"] == "DONE", (s, body))
    s, body = post(C["hrx"], "recruitment/applicant/verification/", {"applicant_id": aid, "complete": True})
    check("complete with pending manual checks -> 400 listing them", s == 400 and "Identity documents" in body["message"], (s, body))
    s, body = post(C["hrx"], "recruitment/applicant/verification/", {"applicant_id": aid, "complete": True, "checks": [
        {"key": "PERSONAL_DETAILS", "status": "DONE"}, {"key": "IDENTITY", "status": "DONE"},
        {"key": "EDUCATION", "status": "DONE"}, {"key": "EXPERIENCE", "status": "WAIVED", "note": "Fresher letter pending"},
        {"key": "POLICE", "label": "Police verification", "status": "DONE"}]})
    check("checks + complete in one call -> ONBOARDING, joining date from offer, custom check kept",
          s == 200 and body["data"]["applicant"]["stage"] == "ONBOARDING" and body["data"]["applicant"]["joining_date"] == "2026-12-10"
          and len(body["data"]["onboarding_checks"]) == 5 and any(c["key"] == "POLICE" for c in body["data"]["verification_checks"]), (s, body))

    # ---- onboarding
    s, body = post(C["hrx"], "recruitment/applicant/onboarding/", {"applicant_id": aid, "access_role_id": roles["HR Executive"].id})
    check("HR Executive cannot set access role (no access.manage) -> 400", s == 400 and "access_role_id" in body.get("errors", {}), (s, body))
    s, body = post(C["hrx"], "recruitment/applicant/onboarding/", {"applicant_id": aid, "onboarding_data": {"salary": 1}})
    check("unknown onboarding_data field -> 400", s == 400, (s, body))
    s, body = post(C["owner"], "recruitment/applicant/onboarding/", {
        "applicant_id": aid, "reports_to_id": mgr.id, "access_role_id": roles["HR Executive"].id,
        "onboarding_data": {"pan_number": "ABCDE1234F", "pf_uan": "100000000099", "bank_ifsc": "HDFC0000001"}})
    check("owner sets manager, access role, statutory data", s == 200 and body["data"]["applicant"]["reports_to"]["id"] == mgr.id, (s, body))
    s, body = post(C["hr"], "recruitment/applicant/convert/", {"applicant_id": aid})
    check("convert with pending onboarding checks -> 400", s == 400 and "Onboarding is not complete" in body["message"], (s, body))
    s, body = post(C["hrx"], "recruitment/applicant/onboarding/", {"applicant_id": aid, "checks": [
        {"key": "JOINING_CONFIRMED", "status": "DONE"}, {"key": "EMPLOYEE_DETAILS", "status": "DONE"}, {"key": "DOCUMENTS", "status": "DONE"}]})
    check("onboarding checks done", s == 200, (s, body))
    s, body = post(C["hrx"], "recruitment/applicant/convert/", {"applicant_id": aid, "create_user": True})
    check("HR Executive asking for a login without employee.create_user -> 403", s == 403, (s, body))

    s, body = post(C["hr"], "recruitment/applicant/convert/", {"applicant_id": aid})
    ok = s == 201
    check("convert by HR Manager -> 201", ok, (s, body))
    if ok:
        d = body["data"]
        emp = Employee.objects.get(pk=d["employee"]["id"])
        check("employee created from applicant (code, names, links, statutory data, ACTIVE)",
              emp.employee_code.startswith("EMP-") and emp.first_name == "Rahul" and emp.personal_email == "rahul.patil@x.test"
              and emp.designation_ref_id == desig.id and emp.designation == "Python Developer" and emp.branch_id == pune.id
              and emp.reports_to_id == mgr.id and emp.access_role_id == roles["HR Executive"].id
              and emp.pan_number == "ABCDE1234F" and emp.joining_date == date(2026, 12, 10) and emp.employment_status == "ACTIVE", emp.__dict__)
        check("salary assignment from accepted offer v2, starting at the cycle start",
              d["salary_assignment"]["effective_from"] == "2026-12-01" and d["salary_assignment"]["monthly_gross"] == "52000.00"
              and d["salary_assignment"]["annual_ctc"] == "646500.00", d["salary_assignment"])
        check("login created (default for a user with employee.create_user) + membership",
              d["user_account"] and emp.user_id and OrganizationMembership.objects.filter(organization=org, user_id=emp.user_id).exists(), d["user_account"])
        check("leave balance for the joining year", EmployeeLeaveBalance.objects.filter(employee=emp, leave_year=2026).count() == 1)
        check("documents copied to the employee", EmployeeDocument.objects.filter(employee=emp).count() == 1)
        check("applicant COMPLETED, all onboarding checks finished, primary action view_employee",
              d["applicant"]["stage"] == "COMPLETED" and all(c["status"] in ("DONE", "WAIVED") for c in d["onboarding_checks"])
              and d["primary_action"] == "view_employee", d["applicant"]["stage"])
        s, body = post(C["hr"], "recruitment/applicant/convert/", {"applicant_id": aid})
        check("convert twice -> 400", s == 400, (s, body))
        s, body = post(C["hrx"], "recruitment/applicant/update/", {"applicant_id": aid, "first_name": "Z"})
        check("converted applicant cannot be edited -> 400", s == 400, (s, body))

    # ---- rejected applicants never become employees
    s, body = post(C["hrx"], "recruitment/applicant/create/", {"first_name": "Amit", "last_name": "S", "email": "amit@x.test", "mobile": "9876500002"})
    bid = body["data"]["applicant"]["id"]
    s, body = post(C["hrx"], "recruitment/applicant/status-update/", {"applicant_id": bid, "status": "REJECTED"})
    check("REJECTED -> stage CLOSED", s == 200 and body["data"]["applicant"]["stage"] == "CLOSED", (s, body))
    s, body = post(C["hr"], "recruitment/applicant/convert/", {"applicant_id": bid})
    check("rejected applicant cannot be converted", s == 400, (s, body))
    s, body = post(C["hrx"], "recruitment/applicant/status-update/", {"applicant_id": bid, "status": "PENDING"})
    check("rejected applicant can be reopened -> APPLICANT", s == 200 and body["data"]["applicant"]["stage"] == "APPLICANT", (s, body))
    check("history is append-only", Applicant.objects.get(pk=bid).history.count() == 3)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", ALLOWED_HOSTS=["*"])
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
