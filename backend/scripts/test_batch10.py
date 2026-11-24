"""
Batch 10 checks: reports app - dashboard (widgets by permission, celebrations
today), reports/list, attendance / leave / payroll / recruitment reports
(json + xlsx, team scope, columns that follow the organization setup).

Run after migrate; any database; everything is rolled back:
    python manage.py shell -c "exec(open('scripts/test_batch10.py').read())"
"""
import sys
import traceback
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import BytesIO

from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from app.accounts.models import AccessRole, Branch, Organization, OrganizationMembership, Permission, Role, User
from app.accounts.services import seed_organization_defaults
from app.attendance.models import AttendanceRecord
from app.employees.models import Department, Employee
from app.leave.models import EmployeeLeaveBalance, LeaveApplication, LeaveType
from app.payroll.models import (
    CompanyStatutorySettings, PayrollLineItem, PayrollRecord, PayrollRun, PayrollSettings,
)
from app.recruitment.models import Applicant

RESULTS = []
D = Decimal
OCT1, OCT31 = date(2026, 10, 1), date(2026, 10, 31)


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
    if r.get("Content-Type", "").startswith("application/vnd.openxmlformats"):
        return r.status_code, r
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.content[:200]}


def aware(day, hh, mm):
    return timezone.make_aware(datetime.combine(day, time(hh, mm)))


def run():
    admin_role, _ = Role.objects.get_or_create(name="Admin", defaults={"is_active": True})
    emp_role, _ = Role.objects.get_or_create(name="Employee", defaults={"is_active": True})
    n = [0]

    def user(name, role=emp_role):
        n[0] += 1
        return User.objects.create(username=f"b10_{name}", email=f"b10_{name}@x.test", mobile=f"10000000{n[0]:02d}",
                                   role=role, first_name=name.title())

    owner = user("owner", admin_role)
    org = Organization.objects.create(organization_name="B10 Org", owner=owner, email="hr@b10.test")
    OrganizationMembership.objects.create(organization=org, user=owner, is_active=True)
    seed_organization_defaults(org)
    roles = {r.name: r for r in AccessRole.objects.filter(organization=org)}
    recruiter_role = AccessRole.objects.create(organization=org, name="Recruiter")
    recruiter_role.permissions.add(Permission.objects.get(code="applicant.view"))
    today = timezone.localdate()

    def employee(name, role=None, **kw):
        u = user(name)
        OrganizationMembership.objects.create(organization=org, user=u, is_active=True)
        return Employee.objects.create(organization=org, first_name=name.title(), last_name="T",
                                       employee_code=f"B10-{name}", user=u, access_role=role,
                                       employment_status="ACTIVE", **kw)

    hr = employee("hr", roles["HR Manager"])
    mgr = employee("mgr", roles["Department Manager"])
    e1 = employee("one", reports_to=mgr, date_of_birth=today.replace(year=1995) if not (today.month == 2 and today.day == 29) else date(1996, 2, 29))
    e2 = employee("two", joining_date=today.replace(year=today.year - 2) if not (today.month == 2 and today.day == 29) else date(2024, 2, 29))
    e3 = employee("three", joining_date=today)          # joined today: not an anniversary
    rec = employee("rec", recruiter_role)
    C = {k: client_for(v.user) for k, v in dict(hr=hr, mgr=mgr, one=e1, two=e2, rec=rec).items()}
    C["owner"] = client_for(owner)

    # attendance: October (reports) + today (dashboard)
    for day in (date(2026, 10, 5), date(2026, 10, 6)):
        AttendanceRecord.objects.create(organization=org, employee=e1, work_date=day, status="PRESENT",
                                        check_in=aware(day, 9, 50), check_out=aware(day, 18, 30),
                                        late_minutes=20, net_work_minutes=520)
        AttendanceRecord.objects.create(organization=org, employee=e2, work_date=day, status="ABSENT")
    AttendanceRecord.objects.create(organization=org, employee=e1, work_date=today, status="INCOMPLETE",
                                    check_in=timezone.now() - timedelta(hours=1), late_minutes=5)

    # leave
    cl = LeaveType.objects.create(organization=org, name="Casual", code="CL", annual_allocation=D("12"))
    EmployeeLeaveBalance.objects.create(organization=org, employee=e1, leave_type=cl, leave_year=2026,
                                        allocated_days=D("12"), used_days=D("2"))
    LeaveApplication.objects.create(organization=org, employee=e1, leave_type=cl, start_date=date(2026, 10, 12),
                                    end_date=date(2026, 10, 13), total_days=D("2"), reason="Trip", status="APPROVED")
    LeaveApplication.objects.create(organization=org, employee=e1, leave_type=cl, start_date=today + timedelta(days=3),
                                    end_date=today + timedelta(days=3), total_days=D("1"), reason="Personal",
                                    status="PENDING")

    # ================= DASHBOARD
    s, b = post(C["one"], "reports/dashboard/")
    w = b.get("data", {})
    mine = {"my_today", "my_month", "my_leave_balance", "my_recent_leaves", "my_work", "celebrations",
            "upcoming_holidays", "announcements"}
    check("plain employee: only personal + everyone widgets", s == 200 and set(w.get("available_widgets", [])) == mine
          and not w.get("failed_widgets"), (s, w.get("available_widgets"), w.get("failed_widgets")))
    check("my_today shows today's punch", w.get("widgets", {}).get("my_today", {}).get("status") == "INCOMPLETE"
          and w["widgets"]["my_today"]["check_in"], w.get("widgets", {}).get("my_today"))
    cel = w.get("widgets", {}).get("celebrations", {})
    check("celebrations today: birthday + work anniversary (2 years), joiner of today not listed",
          [p["employee_id"] for p in cel.get("birthdays", [])] == [e1.id]
          and [(p["employee_id"], p["years"]) for p in cel.get("anniversaries", [])] == [(e2.id, 2)]
          and "date_of_birth" not in str(cel), cel)
    check("my_leave_balance + recent leaves", w["widgets"]["my_leave_balance"][0]["available"] == 10.0
          and len(w["widgets"]["my_recent_leaves"]) == 2, (w["widgets"]["my_leave_balance"], w["widgets"]["my_recent_leaves"]))

    s, b = post(C["mgr"], "reports/dashboard/")
    av = set(b["data"]["available_widgets"])
    check("department manager: team_today + pending_approvals, no org widgets",
          {"team_today", "pending_approvals"} <= av and "org_today" not in av and "payroll_summary" not in av, av)
    check("pending approvals = team's pending leave",
          b["data"]["widgets"]["pending_approvals"]["leave"]["count"] == 1
          and b["data"]["widgets"]["team_today"]["present"] == 1, b["data"]["widgets"].get("pending_approvals"))

    s, b = post(C["hr"], "reports/dashboard/")
    av = set(b["data"]["available_widgets"])
    check("HR manager gets org widgets (today, trend, headcount, leave, recruitment, helpdesk, assets, visitors)",
          {"org_today", "attendance_trend", "headcount", "recent_leave_requests", "recruitment_pipeline",
           "helpdesk", "assets", "visitors_today"} <= av and "payroll_summary" not in av
          and not b["data"]["failed_widgets"], (av, b["data"]["failed_widgets"]))
    ot = b["data"]["widgets"]["org_today"]
    check("org_today counts + recent punches", ot["total"] == 6 and ot["present"] == 1 and len(ot["recent_punches"]) == 0,
          ot)
    check("charts use one shape (type / labels / series)",
          set(b["data"]["widgets"]["attendance_trend"].keys()) == {"type", "labels", "series"}
          and len(b["data"]["widgets"]["attendance_trend"]["labels"]) == 30)

    s, b = post(C["owner"], "reports/dashboard/")
    av = set(b["data"]["available_widgets"])
    check("owner without employee profile: all org widgets, no 'my' widgets, nothing failed",
          "payroll_summary" in av and "receivables" in av and "expenses" in av and "projects" in av
          and "my_today" not in av and not b["data"]["failed_widgets"], (av, b["data"]["failed_widgets"]))
    s, b = post(C["hr"], "reports/dashboard/", {"widgets": ["headcount", "celebrations"]})
    check("widgets parameter loads only those", s == 200 and set(b["data"]["widgets"]) == {"headcount", "celebrations"},
          b["data"]["widgets"].keys() if s == 200 else b)
    s, b = post(C["hr"], "reports/dashboard/", {"widgets": ["nope"]})
    check("unknown widget -> 400", s == 400, s)
    s, b = post(C["one"], "reports/dashboard/", {"widgets": ["payroll_summary"]})
    check("asking for a widget you may not see returns nothing", s == 200 and b["data"]["widgets"] == {}, b)

    # ================= LIST
    s, b = post(C["one"], "reports/list/")
    check("plain employee: no reports", s == 200 and b["data"]["reports"] == [], b)
    s, b = post(C["hr"], "reports/list/")
    keys = [r["key"] for r in b["data"]["reports"]]
    filters = {f["key"] for r in b["data"]["reports"] for f in r["filters"]}
    check("HR manager: attendance, leave, recruitment (no payroll.view_all)",
          keys == ["attendance", "leave", "recruitment"], keys)
    check("no branch filter when the organization has no branches", "branch_id" not in filters, filters)
    s, b = post(C["owner"], "reports/list/")
    check("owner: all 4 reports", [r["key"] for r in b["data"]["reports"]] == ["attendance", "leave", "payroll", "recruitment"])

    # ================= ATTENDANCE
    rng = {"from_date": str(OCT1), "to_date": str(OCT31)}
    s, b = post(C["one"], "reports/attendance/", rng)
    check("plain employee cannot open reports (403)", s == 403, s)
    s, b = post(C["hr"], "reports/attendance/", rng)
    d = b.get("data", {})
    row1 = next((r for r in d.get("rows", []) if r["employee_code"] == "B10-one"), {})
    row2 = next((r for r in d.get("rows", []) if r["employee_code"] == "B10-two"), {})
    cols = [c["key"] for c in d.get("columns", [])]
    check("attendance summary: present / late / absent per employee",
          s == 200 and row1.get("present") == 2 and row1.get("late_minutes") == 40 and row2.get("absent") == 2
          and d["totals"]["absent"] == 2, (s, row1, row2))
    check("no Branch / Department / Remote columns without that setup",
          "branch" not in cols and "department" not in cols and "remote" not in cols, cols)
    s, b = post(C["hr"], "reports/attendance/", {**rng, "view": "daily", "status": "ABSENT"})
    check("absent report = daily view with status ABSENT",
          s == 200 and len(b["data"]["rows"]) == 2 and all(r["status"] == "Absent" for r in b["data"]["rows"]), b)
    s, b = post(C["hr"], "reports/attendance/", {**rng, "late_only": True})
    check("summary late_only", s == 200 and [r["employee_code"] for r in b["data"]["rows"]] == ["B10-one"], b)
    s, b = post(C["mgr"], "reports/attendance/", rng)
    codes = {r["employee_code"] for r in b["data"]["rows"]}
    check("team scope: manager sees only own team", s == 200 and "B10-one" in codes and "B10-two" not in codes
          and b["data"]["filters"]["scope"] == "team", codes)
    s, b = post(C["hr"], "reports/attendance/", {"from_date": "2026-10-31", "to_date": "2026-10-01"})
    check("from_date after to_date -> 400", s == 400, s)
    s, b = post(C["hr"], "reports/attendance/", {**rng, "page_size": 2, "page": 2})
    check("pagination", s == 200 and b["data"]["pagination"]["page"] == 2 and len(b["data"]["rows"]) <= 2
          and b["data"]["pagination"]["total_rows"] >= 3, b.get("data", {}).get("pagination"))
    s, r = post(C["hr"], "reports/attendance/", {**rng, "format": "xlsx"})
    ok = s == 200 and hasattr(r, "content")
    header = []
    if ok:
        from openpyxl import load_workbook
        ws = load_workbook(BytesIO(r.content)).active
        header = [c.value for c in ws[5] if c.value]
    check("Excel download has the same columns", ok and "attachment" in r["Content-Disposition"]
          and header[:3] == ["Code", "Employee", "Present"], header)

    dept = Department.objects.create(organization=org, name="Ops")
    Branch.objects.create(organization=org, name="Pune")
    Employee.objects.filter(pk=e1.pk).update(department_ref=dept)
    s, b = post(C["hr"], "reports/attendance/", rng)
    cols = [c["key"] for c in b["data"]["columns"]]
    s2, b2 = post(C["hr"], "reports/list/")
    check("with departments + branches: columns and filters appear", "department" in cols and "branch" in cols
          and "branch_id" in {f["key"] for f in b2["data"]["reports"][0]["filters"]}, cols)

    # ================= LEAVE
    s, b = post(C["hr"], "reports/leave/", rng)
    check("leave taken in range", s == 200 and len(b["data"]["rows"]) == 1 and b["data"]["rows"][0]["days"] == 2.0
          and b["data"]["summary"]["approved_days"] == 2.0, b)
    s, b = post(C["hr"], "reports/leave/", {"view": "balance", "to_date": "2026-12-31", "from_date": "2026-12-01"})
    row = next(r for r in b["data"]["rows"] if r["employee_code"] == "B10-one")
    check("leave balance per type", s == 200 and row["CL_allocated"] == 12.0 and row["CL_available"] == 10.0, row)

    # ================= PAYROLL
    s, b = post(C["owner"], "reports/payroll/")
    check("no payroll runs -> 404", s == 404, s)
    PayrollSettings.objects.create(organization=org, cycle_start_day=1, payslip_mode="SIMPLE",
                                   late_deduction_enabled=False)
    run1 = PayrollRun.objects.create(organization=org, period_start=OCT1, period_end=OCT31, status="GENERATED")
    rec1 = PayrollRecord.objects.create(payroll_run=run1, organization=org, employee=e1, present_days=D("29"),
                                        absent_days=D("2"), monthly_salary=D("31000"), per_day_rate=D("1000"),
                                        gross_earnings=D("31000"), total_deductions=D("2000"), net=D("29000"))
    PayrollLineItem.objects.create(payroll_record=rec1, component_code="LOP", component_name="Loss of Pay",
                                   component_type="LOP", amount=D("2000"))
    s, b = post(C["hr"], "reports/payroll/")
    check("payroll report needs payroll.view_all", s == 403, s)
    s, b = post(C["owner"], "reports/payroll/", {"month": "2026-10"})
    cols = [c["key"] for c in b["data"]["columns"]]
    check("SIMPLE payroll: gross / LOP / net, no PF / ESI / employer columns",
          s == 200 and b["data"]["rows"][0]["lop"] == 2000.0 and "pf" not in cols and "esi" not in cols
          and "employer_cost" not in cols and "late_deduction" not in cols and b["data"]["totals"]["net"] == 29000.0,
          (cols, b.get("data", {}).get("rows")))
    PayrollSettings.objects.filter(organization=org).update(payslip_mode="FULL")
    CompanyStatutorySettings.objects.create(organization=org, is_pf_applicable=True)
    PayrollRecord.objects.filter(pk=rec1.pk).update(pf_employee=D("1800"), pf_employer=D("550"), eps=D("1250"))
    s, b = post(C["owner"], "reports/payroll/", {"payroll_run_id": run1.id})
    cols = [c["key"] for c in b["data"]["columns"]]
    check("FULL + PF on: PF and employer columns appear, ESI stays hidden",
          "pf" in cols and "pf_employer" in cols and "employer_cost" in cols and "esi" not in cols, cols)
    s, b = post(C["owner"], "reports/payroll/", {"month": "2025-01"})
    check("month without a run -> 404", s == 404, s)

    # ================= RECRUITMENT
    def applicant(code, stage, status, assigned=None, applied=date(2026, 10, 3)):
        return Applicant.objects.create(organization=org, applicant_code=code, first_name=code, last_name="A",
                                        email=f"{code}@c.test", mobile="9000000000", applied_on=applied,
                                        stage=stage, status=status, assigned_to=assigned)
    applicant("A1", "APPLICANT", "PENDING", assigned=rec)
    applicant("A2", "VERIFICATION", "SELECTED")
    applicant("A3", "CLOSED", "REJECTED")
    s, b = post(C["hr"], "reports/recruitment/", rng)
    check("recruitment applicants (all for HR)", s == 200 and len(b["data"]["rows"]) == 3, b)
    s, b = post(C["rec"], "reports/recruitment/", rng)
    check("view-only recruiter sees only assigned applicants", s == 200 and [r["applicant_code"] for r in b["data"]["rows"]] == ["A1"], b)
    s, b = post(C["hr"], "reports/recruitment/", {**rng, "view": "funnel"})
    funnel = {r["stage"]: r for r in b["data"]["rows"]}
    check("funnel: reached counts are cumulative", s == 200 and funnel["Applicant"]["reached"] == 2
          and funnel["Verification"]["reached"] == 1 and funnel["Closed"]["current"] == 1
          and b["data"]["summary"]["applied"] == 3, b.get("data", {}).get("rows"))
    s, r = post(C["hr"], "reports/recruitment/", {**rng, "format": "xlsx"})
    check("recruitment Excel", s == 200 and hasattr(r, "content") and r.content[:2] == b"PK", s)


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
