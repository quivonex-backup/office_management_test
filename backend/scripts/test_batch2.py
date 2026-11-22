"""
Batch 2 checks: permission checks + self/team/all scope on attendance, leave,
reimbursements, employees, payroll; branch geofence for punches.

Run after batch 1 (makemigrations + migrate + seed_org_access); any database;
everything is rolled back at the end:
    python manage.py shell -c "exec(open('scripts/test_batch2.py').read())"

"Allowed" checks only assert that the permission layer let the call through
(status is not 403); the business result of those calls is covered by the
existing flows.
"""
import sys
import traceback
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.db import transaction
from django.test.utils import override_settings
from rest_framework.test import APIClient

from app.accounts.models import AccessRole, Branch, Organization, OrganizationMembership, Role, User
from app.accounts.services import seed_organization_defaults
from app.attendance.models import AttendanceCorrection, AttendanceRecord
from app.attendance.services import get_attendance_settings, verify_office_location
from app.employees.models import Employee
from app.expenses.models import EmployeeReimbursement
from app.leave.models import LeaveApplication, LeaveType

RESULTS = []


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


def ids(body):
    return sorted(row["id"] for row in body.get("data", []))


def emp_ids(body, key="employee"):
    out = set()
    for row in body.get("data", []):
        v = row.get(key) if key in row else row.get("employee_id")
        if isinstance(v, dict):
            v = v.get("id")
        out.add(v)
    return out


def run():
    admin_role, _ = Role.objects.get_or_create(name="Admin", defaults={"is_active": True})
    emp_role, _ = Role.objects.get_or_create(name="Employee", defaults={"is_active": True})

    n = [0]

    def user(name, role=emp_role):
        n[0] += 1
        u = User.objects.create(username=f"b2_{name}", email=f"b2_{name}@x.test", mobile=f"80000000{n[0]:02d}", role=role)
        u.set_password("x-test-123")
        u.save()
        return u

    owner = user("owner", admin_role)
    org = Organization.objects.create(organization_name="B2 Org", owner=owner,
                                      latitude=Decimal("18.520400"), longitude=Decimal("73.856700"))
    OrganizationMembership.objects.create(organization=org, user=owner, is_active=True)
    seed_organization_defaults(org)
    roles = {r.name: r for r in AccessRole.objects.filter(organization=org)}

    def employee(name, role_name=None, manager=None):
        u = user(name)
        OrganizationMembership.objects.create(organization=org, user=u, is_active=True)
        return Employee.objects.create(
            organization=org, first_name=name, last_name="T", employee_code=f"B2-{name}", user=u,
            access_role=roles.get(role_name), reports_to=manager, employment_status="ACTIVE",
        )

    hr = employee("hr", "HR Manager")
    pay = employee("pay", "Payroll Manager")
    mgr = employee("mgr", "Department Manager")
    e1 = employee("e1", manager=mgr)
    e2 = employee("e2", manager=mgr)
    e3 = employee("e3")  # outside mgr's team

    C = {k: client_for(v.user) for k, v in dict(hr=hr, pay=pay, mgr=mgr, e1=e1, e2=e2, e3=e3).items()}
    C["owner"] = client_for(owner)

    day = date.today() - timedelta(days=3)
    recs = {e.first_name: AttendanceRecord.objects.create(organization=org, employee=e, work_date=day, status="PRESENT")
            for e in (hr, pay, mgr, e1, e2, e3)}
    corr = {k: AttendanceCorrection.objects.create(attendance=recs[k], field_name="STATUS", new_value="PRESENT",
                                                   reason="test", requested_by=recs[k].employee.user)
            for k in ("mgr", "e1", "e3")}

    team = {mgr.id, e1.id, e2.id}
    everyone = {hr.id, pay.id, mgr.id, e1.id, e2.id, e3.id}

    # ================= attendance/list
    s, b = post(C["e1"], "attendance/list/")
    check("attendance/list plain employee -> self only",
          s == 200 and b["scope_applied"] == "self" and emp_ids(b) == {e1.id}, (s, b.get("scope_applied"), emp_ids(b)))
    s, b = post(C["e1"], "attendance/list/", {"scope": "all"})
    check("attendance/list employee asking all is clamped to self", s == 200 and b["scope_applied"] == "self", (s, b))
    s, b = post(C["mgr"], "attendance/list/")
    check("attendance/list manager -> team", s == 200 and b["scope_applied"] == "team" and emp_ids(b) == team,
          (s, b.get("scope_applied"), emp_ids(b)))
    s, b = post(C["mgr"], "attendance/list/", {"scope": "self"})
    check("attendance/list manager scope=self", s == 200 and emp_ids(b) == {mgr.id}, emp_ids(b))
    s, b = post(C["hr"], "attendance/list/")
    check("attendance/list HR -> all", s == 200 and b["scope_applied"] == "all" and emp_ids(b) == everyone, emp_ids(b))
    s, b = post(C["owner"], "attendance/list/")
    check("attendance/list owner (no employee row) -> all", s == 200 and b["scope_applied"] == "all", (s, b))
    s, b = post(C["hr"], "attendance/list/", {"scope": "company"})
    check("attendance/list invalid scope -> 400", s == 400, (s, b))

    # ================= attendance/detail
    s, _ = post(C["e1"], "attendance/detail/", {"attendance_id": recs["e1"].id})
    check("attendance/detail own record", s == 200, s)
    s, _ = post(C["e1"], "attendance/detail/", {"attendance_id": recs["e2"].id})
    check("attendance/detail other employee's record -> 403", s == 403, s)
    s, _ = post(C["mgr"], "attendance/detail/", {"attendance_id": recs["e2"].id})
    check("attendance/detail manager, team member", s == 200, s)
    s, _ = post(C["mgr"], "attendance/detail/", {"attendance_id": recs["e3"].id})
    check("attendance/detail manager, outside team -> 403", s == 403, s)

    # ================= corrections
    s, b = post(C["e1"], "attendance/corrections/list/")
    got = {row["attendance"] if not isinstance(row.get("attendance"), dict) else row["attendance"]["id"] for row in b.get("data", [])}
    check("corrections/list employee -> own only", s == 200 and got == {recs["e1"].id}, (s, got))
    s, b = post(C["mgr"], "attendance/corrections/review/", {"correction_id": corr["e3"].id, "approve": True})
    check("correction review outside team -> 403", s == 403 and "outside" in b["message"], (s, b))
    s, b = post(C["mgr"], "attendance/corrections/review/", {"correction_id": corr["mgr"].id, "approve": True})
    check("correction review own request -> 403", s == 403 and "own" in b["message"], (s, b))
    s, b = post(C["e2"], "attendance/corrections/review/", {"correction_id": corr["e1"].id, "approve": True})
    check("correction review without permission -> 403", s == 403, (s, b))
    s, b = post(C["mgr"], "attendance/corrections/review/", {"correction_id": corr["e1"].id, "approve": False,
                                                              "review_note": "no"})
    check("correction review team member passes permission layer", s != 403, (s, b))

    # ================= attendance setup
    s, _ = post(C["e1"], "attendance/shifts/create/", {"name": "X"})
    check("shifts/create plain employee -> 403", s == 403, s)
    s, _ = post(C["owner"], "attendance/shifts/create/", {"name": "General", "start_time": "09:00", "end_time": "18:00"})
    check("shifts/create owner passes", s != 403, s)
    s, _ = post(C["hr"], "attendance/settings/")
    check("attendance/settings HR without settings.manage -> 403", s == 403, s)
    s, _ = post(C["owner"], "attendance/settings/")
    check("attendance/settings owner", s == 200, s)
    s, _ = post(C["mgr"], "attendance/shifts/list/")
    check("shifts/list manager (view_team) allowed", s == 200, s)
    s, _ = post(C["e1"], "attendance/bulk-mark-absent/", {"from_date": str(day), "to_date": str(day)})
    check("bulk-mark-absent plain employee -> 403", s == 403, s)
    s, _ = post(C["e1"], "attendance/my-attendance/")
    check("my-attendance still works for employees", s == 200, s)

    # ================= leave
    lt = LeaveType.objects.create(organization=org, name="Casual", code="CL", annual_allocation=12)
    apps = {e.first_name: LeaveApplication.objects.create(
        organization=org, employee=e, leave_type=lt, start_date=day, end_date=day,
        total_days=1, reason="r") for e in (mgr, e1, e3)}
    s, b = post(C["e1"], "leave/applications/list/")
    check("leave list employee -> self", s == 200 and b["scope_applied"] == "self" and emp_ids(b) <= {e1.id}, (s, b.get("scope_applied")))
    s, b = post(C["mgr"], "leave/applications/list/")
    check("leave list manager -> team", s == 200 and b["scope_applied"] == "team" and emp_ids(b) == {mgr.id, e1.id},
          (s, emp_ids(b)))
    s, b = post(C["hr"], "leave/applications/list/")
    check("leave list HR -> all", s == 200 and b["scope_applied"] == "all" and emp_ids(b) == {mgr.id, e1.id, e3.id}, emp_ids(b))
    s, b = post(C["mgr"], "leave/applications/review/", {"application_id": apps["e3"].id, "decision": "APPROVED"})
    check("leave review outside team -> 403", s == 403, (s, b))
    s, b = post(C["mgr"], "leave/applications/review/", {"application_id": apps["mgr"].id, "decision": "APPROVED"})
    check("leave review own -> 403", s == 403 and "own" in b["message"], (s, b))
    s, b = post(C["e2"], "leave/applications/review/", {"application_id": apps["e1"].id, "decision": "APPROVED"})
    check("leave review without leave.approve -> 403", s == 403, (s, b))
    s, b = post(C["mgr"], "leave/applications/review/", {"application_id": apps["e1"].id, "decision": "REJECTED"})
    check("leave review team member passes permission layer", s != 403, (s, b))
    s, _ = post(C["mgr"], "leave/types/create/", {"name": "X", "code": "X"})
    check("leave types/create without settings.manage -> 403", s == 403, s)
    s, _ = post(C["mgr"], "leave/transactions/list/")
    check("leave transactions/list manager -> 403", s == 403, s)
    s, b = post(C["mgr"], "leave/balances/list/")
    check("leave balances/list manager -> team scope", s == 200 and b["scope_applied"] == "team", (s, b))
    s, _ = post(C["e1"], "leave/types/list/")
    check("leave types/list open to employees", s == 200, s)

    # ================= reimbursements
    def claim(e, n):
        return EmployeeReimbursement.objects.create(
            organization=org, employee=e, reimbursement_number=f"B2-R{n}", title="Taxi",
            expense_type="travel", amount=Decimal("100"), expense_date=day)
    r_e1, r_hr = claim(e1, 1), claim(hr, 2)
    s, b = post(C["e1"], "expenses/reimbursements/list/")
    check("reimbursements/list employee -> self", s == 200 and b["scope_applied"] == "self" and ids(b) == [r_e1.id], (s, b))
    s, b = post(C["hr"], "expenses/reimbursements/list/")
    check("reimbursements/list HR (review) -> all", s == 200 and b["scope_applied"] == "all" and ids(b) == sorted([r_e1.id, r_hr.id]), (s, b))
    s, b = post(C["mgr"], "expenses/reimbursements/list/")
    check("reimbursements/list manager (no review perm) -> self", s == 200 and b["scope_applied"] == "self", (s, b))
    s, _ = post(C["hr"], "expenses/reimbursements/detail/", {"reimbursement_id": r_e1.id})
    check("reimbursements/detail reviewer can open any", s == 200, s)
    s, _ = post(C["e2"], "expenses/reimbursements/detail/", {"reimbursement_id": r_e1.id})
    check("reimbursements/detail other employee -> 404", s == 404, s)
    s, b = post(C["hr"], "expenses/reimbursements/review/", {"reimbursement_id": r_hr.id, "approve": True})
    check("reimbursement review own claim -> 403", s == 403 and "own" in b["message"], (s, b))
    s, b = post(C["mgr"], "expenses/reimbursements/review/", {"reimbursement_id": r_e1.id, "approve": True})
    check("reimbursement review without reimbursement.review -> 403", s == 403, (s, b))
    s, b = post(C["hr"], "expenses/reimbursements/review/", {"reimbursement_id": r_e1.id, "approve": True})
    check("reimbursement review by HR -> APPROVED", s == 200 and b["data"]["status"] == "APPROVED", (s, b))
    s, b = post(C["hr"], "expenses/reimbursements/mark-paid/", {"reimbursement_id": r_e1.id, "payment_method": "upi",
                                                                 "payment_date": str(date.today())})
    check("mark-paid without reimbursement.pay -> 403", s == 403, (s, b))
    s, b = post(C["pay"], "expenses/reimbursements/mark-paid/", {"reimbursement_id": r_e1.id, "payment_method": "upi",
                                                                  "payment_date": str(date.today())})
    check("mark-paid by payroll manager -> PAID", s == 200 and b["data"]["status"] == "PAID", (s, b))

    # ================= employees
    s, b = post(C["e1"], "employees/list/")
    check("employees/list plain employee -> own row", s == 200 and b["scope_applied"] == "self" and ids(b) == [e1.id], (s, b.get("scope_applied"), ids(b)))
    s, b = post(C["mgr"], "employees/list/")
    check("employees/list manager -> team", s == 200 and set(ids(b)) == team, ids(b))
    s, b = post(C["hr"], "employees/list/")
    check("employees/list HR -> all", s == 200 and b["scope_applied"] == "all" and set(ids(b)) == everyone, ids(b))
    s, _ = post(C["mgr"], "employees/detail/", {"employee_id": e3.id})
    check("employees/detail outside team -> 403", s == 403, s)
    s, _ = post(C["mgr"], "employees/detail/", {"employee_id": e2.id})
    check("employees/detail team member", s == 200, s)
    with mock.patch("app.employees.views.upload_to_s3", return_value="stub"):
        s, _ = post(C["e1"], "employees/document/upload/", {"employee_id": e1.id}, multipart=True)
    check("employees/document/upload plain employee -> 403", s == 403, s)

    # ================= payroll
    s, _ = post(C["e1"], "payroll/runs/list/")
    check("payroll runs/list plain employee -> 403", s == 403, s)
    s, _ = post(C["hr"], "payroll/runs/list/")
    check("payroll runs/list HR (no payroll codes) -> 403", s == 403, s)
    s, _ = post(C["pay"], "payroll/runs/list/")
    check("payroll runs/list payroll manager", s == 200, s)
    s, _ = post(C["hr"], "payroll/assignments/list/")
    check("payroll assignments/list HR (salary.assign)", s == 200, s)
    s, _ = post(C["pay"], "payroll/settings/")
    check("payroll settings payroll manager", s == 200, s)
    s, _ = post(C["mgr"], "payroll/records/list/")
    check("payroll records/list manager -> 403 (never team-scoped)", s == 403, s)
    s, _ = post(C["e1"], "payroll/my/payslips/")
    check("payroll my/payslips still open to employees", s != 403, s)

    # ================= branch geofence
    settings_obj = get_attendance_settings(org)
    settings_obj.location_required = True
    settings_obj.allowed_radius_meters = 100
    settings_obj.save()
    mumbai = Branch.objects.create(organization=org, name="Mumbai", latitude=Decimal("19.076000"),
                                   longitude=Decimal("72.877700"), allowed_radius_meters=200)
    no_coords = Branch.objects.create(organization=org, name="NoCoords")
    e1.branch = mumbai
    e1.save(update_fields=["branch"])
    e2.branch = no_coords
    e2.save(update_fields=["branch"])

    r = verify_office_location(org, Decimal("19.076500"), Decimal("72.877700"), 10, settings_obj, employee=e1)
    check("geofence: branch employee at branch -> verified with branch radius",
          r["verified"] and r["branch"]["id"] == mumbai.id and r["allowed_radius_meters"] == 200, r)
    r = verify_office_location(org, Decimal("18.520400"), Decimal("73.856700"), 10, settings_obj, employee=e1)
    check("geofence: branch employee at head office -> rejected", not r["verified"], r)
    r = verify_office_location(org, Decimal("19.076500"), Decimal("72.877700"), 10, settings_obj, employee=e3)
    check("geofence: no branch -> organization location (rejected in Mumbai)", not r["verified"] and r["branch"] is None, r)
    r = verify_office_location(org, Decimal("18.520500"), Decimal("73.856700"), 10, settings_obj, employee=e2)
    check("geofence: branch without coordinates -> organization fallback", r["verified"] and r["branch"] is None, r)
    mumbai.allowed_radius_meters = None
    mumbai.save()
    r = verify_office_location(org, Decimal("19.077200"), Decimal("72.877700"), 10, settings_obj, employee=e1)
    check("geofence: branch radius empty -> settings radius (100 m)", not r["verified"] and r["allowed_radius_meters"] == 100, r)
    r = verify_office_location(org, Decimal("18.520400"), Decimal("73.856700"), 10, settings_obj)
    check("geofence: old call without employee unchanged", r["verified"], r)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", ALLOWED_HOSTS=["*"])
def main():
    try:
        with transaction.atomic():
            with mock.patch("app.communications.notification_service.notify", return_value=None):
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
