"""
Batch 16 checks: attendance/my-attendance/missed-day/ (employee fills an own
day with no punches at once: no approval, no notification).

Run after migrate; any database; everything is rolled back:
    python manage.py shell -c "exec(open('scripts/test_batch16.py').read())"
"""
import sys
import traceback
from datetime import date, datetime, time, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from app.accounts.models import AccessRole, Organization, OrganizationMembership, Role, User
from app.accounts.services import seed_organization_defaults
from app.attendance.models import AttendanceCorrection, AttendancePunch, AttendanceRecord, AttendanceSettings
from app.communications.models import Notification
from app.employees.models import Employee

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


def post(c, url, data=None):
    r = c.post("/" + url, data or {}, format="json")
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.content[:200]}


def iso(day, hh, mm=0):
    return timezone.make_aware(datetime.combine(day, time(hh, mm))).isoformat()


def run():
    admin_role, _ = Role.objects.get_or_create(name="Admin", defaults={"is_active": True})
    emp_role, _ = Role.objects.get_or_create(name="Employee", defaults={"is_active": True})
    n = [0]

    def user(name, role=emp_role):
        n[0] += 1
        return User.objects.create(username=f"b16_{name}", email=f"b16_{name}@x.test", mobile=f"16000000{n[0]:02d}",
                                   role=role, first_name=name.title())

    owner = user("owner", admin_role)
    org = Organization.objects.create(organization_name="B16 Org", owner=owner)
    OrganizationMembership.objects.create(organization=org, user=owner, is_active=True)
    seed_organization_defaults(org)
    roles = {r.name: r for r in AccessRole.objects.filter(organization=org)}
    AttendanceSettings.objects.update_or_create(organization=org, defaults=dict(
        default_start_time=time(9, 0), default_end_time=time(18, 0)))

    def employee(name, role=None, **kw):
        u = user(name)
        OrganizationMembership.objects.create(organization=org, user=u, is_active=True)
        return Employee.objects.create(organization=org, first_name=name.title(), last_name="T",
                                       employee_code=f"B16-{name}", user=u, access_role=role,
                                       employment_status="ACTIVE", joining_date=date(2025, 1, 1), **kw)

    mgr = employee("mgr", roles["Department Manager"])
    dev = employee("dev", reports_to=mgr)
    C = client_for(dev.user)
    today = timezone.localdate()
    d1, d2, d3, d4 = (today - timedelta(days=k) for k in (3, 4, 5, 6))
    URL = "attendance/my-attendance/missed-day/"
    notes_before = Notification.objects.count()

    s, b = post(C, URL, {"work_date": str(d1)})
    check("missing fields -> 400", s == 400 and {"check_in", "check_out", "reason"} <= set(b.get("errors", {})), b)
    s, b = post(C, URL, {"work_date": str(today + timedelta(days=1)), "check_in": iso(today + timedelta(days=1), 9),
                         "check_out": iso(today + timedelta(days=1), 18), "reason": "x"})
    check("future -> 400", s == 400, b)
    s, b = post(C, URL, {"work_date": str(d1), "check_in": iso(d1, 18), "check_out": iso(d1, 9), "reason": "x"})
    check("out before in -> 400", s == 400, b)

    s, b = post(C, URL, {"work_date": str(d1), "check_in": iso(d1, 9, 5), "check_out": iso(d1, 18, 10),
                         "reason": "Forgot phone"})
    rec = AttendanceRecord.objects.filter(employee=dev, work_date=d1).first()
    check("applied at once -> 200, PRESENT", s == 200 and rec and rec.status == "PRESENT" and rec.check_in
          and rec.check_out and b["data"]["attendance"]["status"] == "PRESENT", b)
    check("two APPLIED corrections, unreviewed",
          set(rec.corrections.values_list("field_name", "status")) == {("CHECK_IN", "APPLIED"), ("CHECK_OUT", "APPLIED")}
          and not rec.corrections.filter(reviewed_by__isnull=False).exists())
    check("two manual punches", AttendancePunch.objects.filter(attendance=rec, is_manual=True).count() == 2
          and AttendancePunch.objects.filter(attendance=rec, verification_details__source="employee_direct_missed_day")
          .count() == 2)
    check("no notification sent", Notification.objects.count() == notes_before,
          Notification.objects.count() - notes_before)
    check("response lists corrections", [c["field"] for c in b["data"]["corrections"]] == ["CHECK_IN", "CHECK_OUT"], b)

    s, b = post(C, URL, {"work_date": str(d1), "check_in": iso(d1, 9), "check_out": iso(d1, 18), "reason": "x"})
    check("day with times -> 400", s == 400 and "corrections/create" in b["message"], b)

    AttendanceRecord.objects.create(organization=org, employee=dev, work_date=d2, status="ABSENT")
    s, b = post(C, URL, {"work_date": str(d2), "check_in": iso(d2, 9), "check_out": iso(d2, 12), "reason": "x"})
    rec2 = AttendanceRecord.objects.get(employee=dev, work_date=d2)
    check("ABSENT day reused -> HALF_DAY (3h)", s == 200 and rec2.status == "HALF_DAY", (b, rec2.status))

    s, b = post(C, "attendance/corrections/missed-day/", {"work_date": str(d3), "check_in": iso(d3, 9),
                                                          "check_out": iso(d3, 18), "reason": "x"})
    s, b = post(C, URL, {"work_date": str(d3), "check_in": iso(d3, 9), "check_out": iso(d3, 18), "reason": "x"})
    check("pending approval request for the day -> 400", s == 400 and "pending" in b["message"], b)

    s, b = post(client_for(owner), URL, {"work_date": str(d4), "check_in": iso(d4, 9), "check_out": iso(d4, 18),
                                         "reason": "x"})
    check("user without employee profile -> 404", s == 404, b)

    s, b = post(C, "attendance/corrections/list/", {"scope": "self"})
    ids = {c["id"] for c in b.get("data", [])}
    check("direct entries stay out of corrections/list (same as my-attendance/correct)",
          s == 200 and not (ids & set(rec.corrections.values_list("id", flat=True))), b)


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
print(f"\nBatch 16: {passed}/{len(RESULTS)} passed (all changes rolled back)")
if passed != len(RESULTS):
    sys.exit(1)
