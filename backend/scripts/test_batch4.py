"""
Batch 4 checks: permission codes for clients, vendors, company expenses,
projects, payments, calendar setup and location masters; employee exit
closes assignments; bulk-mark-absent date rule; employees/update JSON body;
leave audit log; attendance Celery tasks.

Run after makemigrations + migrate + seed_org_access; any database;
everything is rolled back at the end:
    python manage.py shell -c "exec(open('scripts/test_batch4.py').read())"
"""
import sys
import traceback
from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest import mock

from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from app.accounts.models import AccessRole, AccessRolePermission, Organization, OrganizationMembership, Permission, Role, User
from app.accounts.permission_catalog import DEFAULT_ACCESS_ROLES
from app.accounts.services import seed_organization_defaults
from app.attendance.models import AttendanceRecord, AttendanceSettings, EmployeeShiftAssignment, Shift
from app.audit.models import ActivityLog
from app.clients.models import Client
from app.employees.models import Employee, EmployeeDocument
from app.payroll.models import EmployeeSalaryAssignment, SalaryStructure
from app.projects.models import Project

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


def run():
    admin_role, _ = Role.objects.get_or_create(name="Admin", defaults={"is_active": True})
    emp_role, _ = Role.objects.get_or_create(name="Employee", defaults={"is_active": True})
    n = [0]

    def user(name, role=emp_role, superuser=False):
        n[0] += 1
        u = User.objects.create(username=f"b4_{name}", email=f"b4_{name}@x.test", mobile=f"60000000{n[0]:02d}",
                                role=role, is_superuser=superuser, is_staff=superuser)
        u.set_password("x-test-123")
        u.save()
        return u

    owner = user("owner", admin_role)
    org = Organization.objects.create(organization_name="B4 Org", owner=owner)
    OrganizationMembership.objects.create(organization=org, user=owner, is_active=True)
    seed_organization_defaults(org)
    roles = {r.name: r for r in AccessRole.objects.filter(organization=org)}
    business = AccessRole.objects.create(organization=org, name="Business Lead")
    for code in ("project.manage", "client.manage"):
        AccessRolePermission.objects.create(access_role=business, permission=Permission.objects.get(code=code))

    def employee(name, role=None, **kw):
        u = user(name)
        OrganizationMembership.objects.create(organization=org, user=u, is_active=True)
        return Employee.objects.create(organization=org, first_name=name.title(), last_name="T",
                                       employee_code=f"B4-{name}", user=u, access_role=role,
                                       employment_status="ACTIVE", **kw)

    plain = employee("plain")
    hr = employee("hr", roles["HR Manager"])
    pay = employee("pay", roles["Payroll Manager"])
    biz = employee("biz", business)
    su = user("su", None, superuser=True)
    C = {k: client_for(v.user) for k, v in dict(plain=plain, hr=hr, pay=pay, biz=biz).items()}
    C["owner"], C["su"] = client_for(owner), client_for(su)

    # ================= catalog + defaults
    check("new codes in catalog", Permission.objects.filter(code__in=[
        "client.manage", "vendor.manage", "project.manage", "payment.manage", "expense.manage", "calendar.manage"]).count() == 6)
    check("new org: HR Manager has calendar.manage, Payroll Manager has expense.manage + vendor.manage",
          roles["HR Manager"].permissions.filter(code="calendar.manage").exists()
          and roles["Payroll Manager"].permissions.filter(code__in=["expense.manage", "vendor.manage"]).count() == 2)
    from app.accounts.management.commands.seed_org_access import _add_missing_default_codes
    AccessRolePermission.objects.filter(access_role=roles["HR Manager"], permission__code="calendar.manage").delete()
    added = _add_missing_default_codes(org)
    check("seed_org_access --update-defaults adds missing default codes (never removes)",
          added == 1 and roles["HR Manager"].permissions.filter(code="calendar.manage").exists(), added)

    # ================= module permissions
    cli = Client.objects.create(organization=org, client_code="B4-CLI", client_name="Acme")
    prj = Project.objects.create(organization=org, project_code="B4-PRJ", project_name="Portal", client=cli)
    for url, data in [
        ("clients/list/", {}), ("clients/create/", {"client_name": "X"}),
        ("vendors/list/", {}), ("vendors/create/", {"vendor_name": "X"}),
        ("expenses/list/", {}), ("expenses/recurring/list/", {}),
        ("projects/list/", {}), ("projects/create/", {"project_name": "X"}),
        ("projects/team-allocation/list/", {}),
        ("payments/project/payment-list/", {}),
        ("calendar/holidays/create/", {"name": "X", "date": "2026-12-25"}),
        ("calendar/weekly-offs/list/", {}),
    ]:
        s, _ = post(C["plain"], url, data)
        check(f"plain employee -> 403 on {url}", s == 403, s)
    for url in ("calendar/holidays/list/", "calendar/employee/", "projects/my-projects/", "location_master/states/list/"):
        s, _ = post(C["plain"], url)
        check(f"plain employee still allowed: {url}", s != 403, s)

    for url in ("clients/list/", "projects/list/", "payments/project/payment-list/", "expenses/list/", "vendors/list/"):
        s, _ = post(C["owner"], url)
        check(f"owner allowed: {url}", s == 200, s)
    s, _ = post(C["biz"], "projects/list/")
    check("project.manage: projects/list", s == 200, s)
    s, _ = post(C["biz"], "clients/list/")
    check("project.manage + client.manage: clients/list", s == 200, s)
    s, _ = post(C["biz"], "payments/project/payment-list/")
    check("project.manage without payment.manage: payments -> 403", s == 403, s)
    s, _ = post(C["biz"], "projects/task/list/", {"project_id": prj.id})
    check("project.manage is ADMIN on tasks of any project", s == 200, s)
    s, _ = post(C["plain"], "projects/task/list/", {"project_id": prj.id})
    check("unallocated employee -> 403 on project tasks (unchanged)", s == 403, s)
    s, _ = post(C["pay"], "expenses/list/")
    check("Payroll Manager: expenses/list", s == 200, s)
    s, _ = post(C["pay"], "vendors/list/")
    check("Payroll Manager: vendors/list", s == 200, s)
    s, _ = post(C["hr"], "calendar/holidays/create/", {"name": "Christmas", "date": "2026-12-25"})
    check("HR Manager (calendar.manage) passes on holidays/create", s != 403, s)
    s, _ = post(C["hr"], "calendar/weekly-offs/list/")
    check("HR Manager weekly-offs/list", s == 200, s)
    s, b = post(C["owner"], "location_master/states/create/", {"state_name": "Test State"})
    check("owner (not super admin) -> 403 on location_master/states/create", s == 403 and "super admin" in b.get("message", ""), (s, b))
    s, _ = post(C["su"], "location_master/states/create/", {"state_name": "Test State"})
    check("super admin passes on location_master/states/create", s != 403, s)

    # ================= bulk-mark-absent date rule
    AttendanceSettings.objects.update_or_create(organization=org, defaults={"auto_mark_absent": True})
    today = timezone.localdate()
    s, b = post(C["owner"], "attendance/bulk-mark-absent/", {"from_date": str(today - timedelta(days=1)), "to_date": str(today)})
    check("bulk-mark-absent including today -> 400", s == 400 and "yesterday" in b["message"], (s, b))

    # ================= employee exit closes assignments
    shift = Shift.objects.create(organization=org, name="Day", start_time=time(0, 0), end_time=time(23, 59))
    structure = SalaryStructure.objects.create(organization=org, name="S", code="S1")
    lwd = today - timedelta(days=5)
    leaver = employee("leaver")
    EmployeeShiftAssignment.objects.create(organization=org, employee=leaver, shift=shift, effective_from=today - timedelta(days=60))
    EmployeeShiftAssignment.objects.create(organization=org, employee=leaver, shift=shift, effective_from=today + timedelta(days=30))
    EmployeeSalaryAssignment.objects.create(organization=org, employee=leaver, salary_structure=structure,
                                            effective_from=today - timedelta(days=60))
    s, b = post(C["owner"], "employees/deactivate/", {"employee_id": leaver.id, "last_working_day": str(lwd)})
    d = b.get("data", {})
    check("deactivate closes running shift + salary assignments at the last working day",
          s == 200 and d.get("closed_shift_assignments") == 1 and d.get("closed_salary_assignments") == 1
          and d.get("future_shift_assignments") == 1
          and EmployeeSalaryAssignment.objects.get(employee=leaver).effective_to == lwd, (s, b))
    s, b = post(C["owner"], "employees/deactivate/", {"employee_id": plain.id, "last_working_day": "31-12-2026"})
    check("deactivate with a bad date -> 400", s == 400, (s, b))

    # ================= employees/update JSON body with remove_document_ids
    doc = EmployeeDocument.objects.create(employee=hr, title="old.pdf")
    with mock.patch("app.employees.views.delete_from_s3", return_value=None):
        s, b = post(C["owner"], "employees/update/", {"employee_id": hr.id, "middle_name": "K", "remove_document_ids": [doc.id]})
    check("employees/update with JSON body + remove_document_ids works",
          s == 200 and not EmployeeDocument.objects.filter(pk=doc.pk).exists(), (s, b))

    # ================= leave audit
    before = ActivityLog.objects.filter(module="LEAVE").count()
    s, b = post(C["owner"], "leave/types/create/", {"name": "Casual", "code": "CL", "annual_allocation": 12})
    check("leave types/create writes an activity log row",
          s in (200, 201) and ActivityLog.objects.filter(module="LEAVE").count() == before + 1, (s, b))
    s, _ = post(C["plain"], "leave/types/create/", {"name": "X", "code": "X"})
    check("refused leave call writes no log row", ActivityLog.objects.filter(module="LEAVE").count() == before + 1)

    # ================= celery tasks (run inline)
    from app.attendance.tasks import auto_mark_absent_task, flag_stale_attendance_task
    AttendanceSettings.objects.filter(organization=org).update(absent_after_minutes=0)
    worker = employee("worker")
    EmployeeShiftAssignment.objects.create(organization=org, employee=worker, shift=shift, effective_from=today - timedelta(days=10))
    joiner = employee("joiner", joining_date=today + timedelta(days=3))
    EmployeeShiftAssignment.objects.create(organization=org, employee=joiner, shift=shift, effective_from=today - timedelta(days=10))
    result = auto_mark_absent_task()
    rec = AttendanceRecord.objects.filter(employee=worker, work_date=today).first()
    check("auto_mark_absent_task marks a no-show ABSENT", rec is not None and rec.status == "ABSENT", (result, rec and rec.status))
    check("auto_mark_absent_task skips a future joiner",
          not AttendanceRecord.objects.filter(employee=joiner, work_date=today).exists(), result)

    stale_day = today - timedelta(days=2)
    start = timezone.make_aware(datetime.combine(stale_day, time(9, 0)))
    stale = AttendanceRecord.objects.create(organization=org, employee=hr, work_date=stale_day, status="INCOMPLETE",
                                            check_in=start, scheduled_start=start, scheduled_end=start + timedelta(hours=9),
                                            overtime_minutes=30)
    fresh = AttendanceRecord.objects.create(organization=org, employee=pay, work_date=today, status="INCOMPLETE",
                                            check_in=timezone.now(), scheduled_end=timezone.now() + timedelta(hours=8))
    result = flag_stale_attendance_task()
    stale.refresh_from_db()
    fresh.refresh_from_db()
    check("flag_stale_attendance_task: old open session -> PENDING_REVIEW, overtime cleared",
          stale.status == "PENDING_REVIEW" and stale.overtime_minutes == 0, (result, stale.status))
    check("flag_stale_attendance_task leaves today's open session", fresh.status == "INCOMPLETE", fresh.status)


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
