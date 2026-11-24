"""
Batch 12 checks: attendance kiosk devices (CRUD + permission) and the two
kiosk APIs (login, punch). Face match and S3 upload are mocked.

Run after migrate; any database; everything is rolled back:
    python manage.py shell -c "exec(open('scripts/test_batch12.py').read())"
"""
import sys
import traceback
from datetime import datetime, time
from decimal import Decimal
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from app.accounts.models import AccessRole, Branch, Organization, OrganizationMembership, Role, User
from app.accounts.services import seed_organization_defaults
from app.attendance.models import AttendanceDevice, AttendancePunch, AttendanceRecord, AttendanceSettings
from app.employees.models import Employee

RESULTS = []
TODAY = timezone.localdate()


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print(("PASS " if condition else "FAIL ") + name + ("" if condition else f"  -> {detail}"))


class Rollback(Exception):
    pass


def client_for(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def post(c, url, data=None, fmt="json"):
    r = c.post("/" + url, data or {}, format=fmt)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.content[:200]}


def at(hh, mm=0):
    return timezone.make_aware(datetime.combine(TODAY, time(hh, mm)))


def kiosk(token=None):
    c = APIClient()
    if token:
        c.credentials(HTTP_AUTHORIZATION=f"Device {token}")
    return c


def selfie():
    from io import BytesIO
    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (20, 20), (200, 160, 120)).save(buf, "JPEG")
    return SimpleUploadedFile("face.jpg", buf.getvalue(), content_type="image/jpeg")


FACE_OK = {"verified": True, "similarity": 0.81, "threshold": 0.36}
FACE_BAD = {"verified": False, "similarity": 0.10, "threshold": 0.36}


def run():
    admin_role, _ = Role.objects.get_or_create(name="Admin", defaults={"is_active": True})
    emp_role, _ = Role.objects.get_or_create(name="Employee", defaults={"is_active": True})
    n = [0]

    def user(name, role=emp_role):
        n[0] += 1
        return User.objects.create(username=f"b12_{name}", email=f"b12_{name}@x.test", mobile=f"12000000{n[0]:02d}",
                                   role=role, first_name=name.title())

    owner = user("owner", admin_role)
    org = Organization.objects.create(organization_name="B12 Org", owner=owner,
                                      latitude=Decimal("19.076000"), longitude=Decimal("72.877700"))
    OrganizationMembership.objects.create(organization=org, user=owner, is_active=True)
    seed_organization_defaults(org)
    roles = {r.name: r for r in AccessRole.objects.filter(organization=org)}
    branch = Branch.objects.create(organization=org, name="Mumbai HQ", latitude=Decimal("19.076000"),
                                   longitude=Decimal("72.877700"), allowed_radius_meters=200)
    AttendanceSettings.objects.update_or_create(organization=org, defaults=dict(
        photo_required=True, location_required=True, default_start_time=time(9, 0), default_end_time=time(18, 0)))

    other_owner = user("other_owner", admin_role)
    other = Organization.objects.create(organization_name="B12 Other", owner=other_owner)
    other_branch = Branch.objects.create(organization=other, name="Elsewhere")

    def employee(name, role=None, o=org, **kw):
        u = user(name)
        OrganizationMembership.objects.create(organization=o, user=u, is_active=True)
        return Employee.objects.create(organization=o, first_name=name.title(), last_name="T",
                                       employee_code=f"B12-{name}", user=u, access_role=role,
                                       employment_status="ACTIVE", **kw)

    hr = employee("hr", roles["HR Manager"])
    plain = employee("plain", branch=branch)
    remote = employee("remote", attendance_location_exempt=True)
    outsider = employee("outsider", o=other)
    C = {"owner": client_for(owner), "hr": client_for(hr.user), "plain": client_for(plain.user)}

    # ================= DEVICE CRUD
    s, b = post(C["plain"], "attendance/device/list/")
    check("plain employee -> 403 on devices", s == 403, s)
    s, b = post(C["hr"], "attendance/device/create/", {"name": "Lobby tablet", "branch_id": branch.id})
    dev = b.get("data") or {}
    check("HR Manager creates device: auto code + password, branch",
          s == 201 and dev["device_code"].startswith("KSK-") and len(dev["password"]) == 14
          and dev["branch"]["name"] == "Mumbai HQ" and dev["logged_in"] is False, b)
    s, b = post(C["owner"], "attendance/device/create/", {"name": "Gate", "device_code": "gate-01"})
    check("custom code stored upper-case", s == 201 and b["data"]["device_code"] == "GATE-01", b)
    s, b = post(C["owner"], "attendance/device/create/", {"name": "Dup", "device_code": "GATE-01"})
    check("duplicate device_code -> 400", s == 400 and "device_code" in b.get("errors", {}), b)
    s, b = post(C["owner"], "attendance/device/create/", {"name": "Bad", "device_code": "a b"})
    check("invalid device_code -> 400", s == 400, b)
    s, b = post(C["owner"], "attendance/device/create/", {"name": "X", "branch_id": other_branch.id})
    check("other org's branch -> 400", s == 400 and "branch_id" in b.get("errors", {}), b)
    s, b = post(C["owner"], "attendance/device/list/")
    rows = b["data"] if s == 200 else []
    check("list shows passwords", s == 200 and len(rows) == 2 and all(r["password"] for r in rows), b)
    s, b = post(C["owner"], "attendance/device/list/", {"search": "lobby"})
    check("list search", s == 200 and [r["name"] for r in b["data"]] == ["Lobby tablet"], b)
    s, b = post(C["owner"], "attendance/device/update/", {"device_id": dev["id"], "name": "Lobby Tab", "notes": "Ground"})
    check("update name / notes", s == 200 and b["data"]["name"] == "Lobby Tab" and b["data"]["notes"] == "Ground", b)
    s, b = post(client_for(other_owner), "attendance/device/update/", {"device_id": dev["id"], "name": "Hack"})
    check("other org cannot touch device -> 404", s == 404, s)

    code, password = dev["device_code"], dev["password"]

    # ================= KIOSK LOGIN
    s, b = post(kiosk(), "attendance/kiosk/login/", {"device_code": code, "password": "wrong"})
    check("wrong password -> 400", s == 400, b)
    s, b = post(kiosk(), "attendance/kiosk/login/", {"device_code": code.lower(), "password": password})
    token = (b.get("data") or {}).get("token", "")
    check("login (code case-insensitive) -> token + device + org",
          s == 200 and token.startswith("dvc_") and b["data"]["device"]["branch"]["name"] == "Mumbai HQ"
          and b["data"]["organization"]["name"] == "B12 Org", b)
    d = AttendanceDevice.objects.get(pk=dev["id"])
    check("only the token's sha256 is stored", d.token_hash and len(d.token_hash) == 64 and token not in d.token_hash
          and d.last_login_at, d.token_hash)
    s, b = post(C["owner"], "attendance/device/list/")
    check("list shows logged_in", any(r["logged_in"] for r in b["data"] if r["id"] == dev["id"]), b)

    # ================= KIOSK PUNCH
    s, b = post(kiosk(), "attendance/kiosk/punch/", {"punch_type": "CHECK_IN", "employee_code": "B12-plain"})
    check("no token -> 401", s == 401 and b["message"] == "Device not logged in.", b)
    s, b = post(kiosk("dvc_bogus"), "attendance/kiosk/punch/", {"punch_type": "CHECK_IN", "employee_code": "B12-plain"})
    check("bad token -> 401", s == 401, b)

    K = kiosk(token)
    near = {"latitude": "19.076100", "longitude": "72.877800", "gps_accuracy_meters": "10"}
    far = {"latitude": "19.200000", "longitude": "72.877700", "gps_accuracy_meters": "10"}

    def punch(data, face=FACE_OK, when=at(9, 5)):
        with mock.patch("app.attendance.services.verify_employee_face", return_value=face), \
                mock.patch("app.attendance.services.upload_to_s3", return_value="attendance/selfies/x.jpg"), \
                mock.patch("django.utils.timezone.now", return_value=when):
            return post(K, "attendance/kiosk/punch/", data, fmt="multipart")

    s, b = punch({"punch_type": "CHECK_IN", "employee_code": "B12-plain", **near})
    check("photo_required: no selfie -> 400", s == 400 and "selfie" in b["message"].lower(), b)
    s, b = punch({"punch_type": "CHECK_OUT", "employee_code": "B12-plain", "selfie": selfie(), **near})
    check("check-out button without check-in -> 400", s == 400 and "Check in first" in b["message"], b)
    s, b = punch({"punch_type": "CHECK_IN", "employee_code": "B12-plain", "selfie": selfie(), **near}, face=FACE_BAD)
    check("face mismatch -> 400", s == 400 and "Face does not match" in b["message"], b)
    s, b = punch({"punch_type": "CHECK_IN", "employee_code": "B12-plain", "selfie": selfie(), **far})
    check("outside branch radius -> 400", s == 400 and "outside" in b["message"], b)
    s, b = punch({"punch_type": "CHECK_IN", "employee_code": "B12-outsider", "selfie": selfie(), **near})
    check("other org's employee -> 404", s == 404 and b["message"] == "Employee not found.", b)
    s, b = punch({"punch_type": "CHECK_IN", "employee_code": "b12-PLAIN", "selfie": selfie(), **near})
    data = b.get("data") or {}
    check("check-in (code case-insensitive) -> 201 like mobile + employee",
          s == 201 and b["message"] == "Check-in recorded successfully." and data["punch"]["punch_type"] == "CHECK_IN"
          and data["employee"]["employee_code"] == "B12-plain" and "attendance" in data
          and "source" not in data["punch"], b)
    p = AttendancePunch.objects.filter(attendance__employee=plain).order_by("-id").first()
    check("verification_details has source KIOSK + device", p and p.verification_details.get("source") == "KIOSK"
          and p.verification_details.get("device_id") == dev["id"] and p.recorded_by_id is None and p.face_verified,
          p and p.verification_details)
    check("one punch only (rejected tries saved nothing)", AttendancePunch.objects.filter(attendance__employee=plain).count() == 1)
    s, b = punch({"punch_type": "CHECK_IN", "employee_code": "B12-plain", "selfie": selfie(), **near}, when=at(12))
    check("check-in button again -> 400 'Already checked in'", s == 400 and "Already checked in" in b["message"], b)
    s, b = punch({"punch_type": "CHECK_OUT", "employee_code": "B12-plain", "selfie": selfie(), **near}, when=at(18, 10))
    check("check-out -> 201", s == 201 and b["message"] == "Check-out recorded successfully.", b)
    rec = AttendanceRecord.objects.get(employee=plain, work_date=TODAY)
    check("record complete", rec.check_in and rec.check_out, rec.status)

    s, b = post(client_for(plain.user), "attendance/my-attendance/", {"work_date": str(TODAY)})
    body = str(b)
    check("employee sees the kiosk punch in my-attendance", s == 200 and str(rec.id) in body, b)

    s, b = punch({"punch_type": "CHECK_IN", "employee_code": "B12-remote", "selfie": selfie(), **far})
    check("remote-exempt employee: any location", s == 201, b)

    AttendanceSettings.objects.filter(organization=org).update(photo_required=False, location_required=False)
    s, b = punch({"punch_type": "CHECK_IN", "employee_code": "B12-hr"})
    check("settings off: no selfie, no location -> 201", s == 201, b)
    AttendanceSettings.objects.filter(organization=org).update(location_required=True)
    s, b = punch({"punch_type": "CHECK_OUT", "employee_code": "B12-hr"}, when=at(18, 30))
    check("location_required: missing GPS -> 400", s == 400, b)
    AttendanceSettings.objects.filter(organization=org).update(location_required=False)

    d.refresh_from_db()
    check("last_seen_at updated", d.last_seen_at is not None)

    # ================= SESSION ENDINGS
    s, b = post(kiosk(), "attendance/kiosk/login/", {"device_code": code, "password": password})
    token2 = b["data"]["token"]
    s, b = punch({"punch_type": "CHECK_OUT", "employee_code": "B12-hr"}, when=at(18, 30))
    check("re-login invalidates the old token -> 401", s == 401 and "Log in again" in b["message"], b)
    K = kiosk(token2)
    s, b = punch({"punch_type": "CHECK_OUT", "employee_code": "B12-hr"}, when=at(18, 30))
    check("new token works", s == 201, b)

    s, b = post(C["owner"], "attendance/device/reset-password/", {"device_id": dev["id"]})
    new_pw = b["data"]["password"]
    check("reset password -> new password, logged out", s == 200 and new_pw != password and not b["data"]["logged_in"], b)
    s, b = punch({"punch_type": "CHECK_IN", "employee_code": "B12-hr"})
    check("after reset: old token -> 401", s == 401, b)
    s, b = post(kiosk(), "attendance/kiosk/login/", {"device_code": code, "password": password})
    check("old password no longer works", s == 400, b)

    # lock after 5 wrong
    for _ in range(5):
        post(kiosk(), "attendance/kiosk/login/", {"device_code": code, "password": "nope"})
    s, b = post(kiosk(), "attendance/kiosk/login/", {"device_code": code, "password": new_pw})
    check("5 wrong passwords -> locked 423 (even with the right one)", s == 423, b)
    s, b = post(C["owner"], "attendance/device/reset-password/", {"device_id": dev["id"]})
    new_pw = b["data"]["password"]
    s, b = post(kiosk(), "attendance/kiosk/login/", {"device_code": code, "password": new_pw})
    check("reset password clears the lock", s == 200, b)
    K = kiosk(b["data"]["token"])

    s, b = post(C["owner"], "attendance/device/update/", {"device_id": dev["id"], "device_code": "LOBBY-1"})
    check("code change logs the device out", s == 200 and not b["data"]["logged_in"], b)
    s, b = punch({"punch_type": "CHECK_IN", "employee_code": "B12-hr"})
    check("after code change -> 401", s == 401, b)
    s, b = post(kiosk(), "attendance/kiosk/login/", {"device_code": "LOBBY-1", "password": new_pw})
    K = kiosk(b["data"]["token"])

    s, b = post(C["hr"], "attendance/device/deactivate/", {"device_id": dev["id"]})
    check("deactivate", s == 200, b)
    s, b = punch({"punch_type": "CHECK_IN", "employee_code": "B12-hr"})
    check("deactivated device: token -> 401", s == 401, b)
    s, b = post(kiosk(), "attendance/kiosk/login/", {"device_code": "LOBBY-1", "password": new_pw})
    check("deactivated device: login -> 403", s == 403, b)
    s, b = post(C["owner"], "attendance/device/list/")
    check("list hides inactive by default", s == 200 and dev["id"] not in [r["id"] for r in b["data"]], b)
    s, b = post(C["owner"], "attendance/device/list/", {"include_inactive": True})
    check("include_inactive", dev["id"] in [r["id"] for r in b["data"]], b)
    s, b = post(C["owner"], "attendance/device/update/", {"device_id": dev["id"], "is_active": True})
    check("reactivate via update", s == 200 and b["data"]["is_active"], b)

    from app.accounts.permission_catalog import PERMISSIONS
    check("permission attendance.device_manage in catalog",
          any(p[0] == "attendance.device_manage" for p in PERMISSIONS))


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
print(f"\nBatch 12: {passed}/{len(RESULTS)} passed (all changes rolled back)")
if passed != len(RESULTS):
    sys.exit(1)
