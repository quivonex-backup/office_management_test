"""
Batch 5 checks: remote / work-from-home punch flag, applicant.assigned_to as an
employee, offer letter PDF + email + public accept / decline link.

Run after makemigrations + migrate; any database; everything is rolled back:
    python manage.py shell -c "exec(open('scripts/test_batch5.py').read())"
"""
import re
import sys
import traceback
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.db import transaction
from django.test import Client as BrowserClient, TestCase
from django.test.utils import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from app.accounts.models import AccessRole, Organization, OrganizationMembership, Role, User
from app.accounts.services import seed_organization_defaults
from app.attendance.services import get_attendance_settings, verify_office_location
from app.employees.models import Designation, Employee
from app.payroll.models import PayrollSettings, SalaryComponent, SalaryStructure, SalaryStructureComponent
from app.recruitment.models import ApplicantOffer

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
        body = {"raw": r.content[:200], "content_type": r.get("Content-Type")}
    return r.status_code, body, r


def run():
    admin_role, _ = Role.objects.get_or_create(name="Admin", defaults={"is_active": True})
    emp_role, _ = Role.objects.get_or_create(name="Employee", defaults={"is_active": True})
    n = [0]

    def user(name, role=emp_role):
        n[0] += 1
        u = User.objects.create(username=f"b5_{name}", email=f"b5_{name}@x.test", mobile=f"50000000{n[0]:02d}", role=role)
        u.set_password("x-test-123")
        u.save()
        return u

    owner = user("owner", admin_role)
    org = Organization.objects.create(organization_name="B5 Org", owner=owner, email="hr@b5.test",
                                      latitude=D("18.520400"), longitude=D("73.856700"))
    OrganizationMembership.objects.create(organization=org, user=owner, is_active=True)
    seed_organization_defaults(org)
    roles = {r.name: r for r in AccessRole.objects.filter(organization=org)}

    def employee(name, role_name=None, **kw):
        u = user(name)
        OrganizationMembership.objects.create(organization=org, user=u, is_active=True)
        return Employee.objects.create(organization=org, first_name=name.title(), last_name="T",
                                       employee_code=f"B5-{name}", user=u, access_role=roles.get(role_name),
                                       employment_status="ACTIVE", **kw)

    hr = employee("hr", "HR Manager")
    mgr = employee("mgr", "Department Manager")
    plain = employee("plain")
    C = {k: client_for(v.user) for k, v in dict(hr=hr, mgr=mgr, plain=plain).items()}
    C["owner"] = client_for(owner)

    # ================= remote / work-from-home flag
    st = get_attendance_settings(org)
    st.location_required = True
    st.allowed_radius_meters = 100
    st.save()
    far = (D("28.613900"), D("77.209000"))   # Delhi, office is in Pune
    r = verify_office_location(org, far[0], far[1], 30, st, employee=plain)
    check("normal employee far from office -> rejected", not r["verified"], r)
    s, b, _ = post(C["owner"], "employees/update/", {"employee_id": plain.id, "attendance_location_exempt": "true"}, multipart=True)
    check("employees/update sets attendance_location_exempt", s == 200 and b["data"]["attendance_location_exempt"] is True, (s, b))
    plain.refresh_from_db()
    r = verify_office_location(org, far[0], far[1], 5000, st, employee=plain)
    check("remote employee: any location accepted, distance still recorded, GPS accuracy ignored",
          r["verified"] and r["location_exempt"] and r["distance_meters"] and r["distance_meters"] > 100000, r)
    r = verify_office_location(org, None, None, None, st, employee=plain)
    check("remote employee without GPS -> still accepted", r["verified"], r)
    s, b, _ = post(C["owner"], "employees/detail/", {"employee_id": plain.id})
    check("flag returned in employees/detail", s == 200 and b["data"].get("attendance_location_exempt") is True, (s, b.get("data", {}).get("attendance_location_exempt")))
    s, b, _ = post(C["plain"], "employees/update/", {"employee_id": plain.id, "attendance_location_exempt": "false"}, multipart=True)
    check("employee cannot change their own flag (needs employee.update)", s == 403, s)

    # ================= payroll + recruitment setup
    PayrollSettings.objects.create(organization=org, cycle_start_day=1, payslip_mode="SIMPLE")
    basic = SalaryComponent.objects.create(organization=org, name="Basic", code="BASIC", component_type="EARNING",
                                           calculation_type="PERCENTAGE", component_role="BASIC")
    special = SalaryComponent.objects.create(organization=org, name="Special allowance", code="SPECIAL",
                                             component_type="EARNING", calculation_type="FIXED", component_role="ALLOWANCE")
    structure = SalaryStructure.objects.create(organization=org, name="Standard", code="STD")
    SalaryStructureComponent.objects.create(salary_structure=structure, salary_component=basic, percentage=D("50"))
    SalaryStructureComponent.objects.create(salary_structure=structure, salary_component=special, amount=D("0"), is_balancing=True)
    desig = Designation.objects.create(organization=org, name="Accountant")

    # ================= assigned_to is an employee
    base = {"first_name": "Priya", "last_name": "Shah", "email": "priya@cand.test", "mobile": "9811100001",
            "designation_id": desig.id}
    s, b, _ = post(C["hr"], "recruitment/applicant/create/", {**base, "assigned_to_id": hr.user_id + 999})
    check("assigned_to_id must be an employee id (bad id -> 400)", s == 400 and "assigned_to_id" in b.get("errors", {}), (s, b))
    s, b, _ = post(C["hr"], "recruitment/applicant/create/", {**base, "assigned_to_id": mgr.id})
    ok = s == 201
    check("applicant created with assigned_to = employee", ok and b["data"]["applicant"]["assigned_to"]["id"] == mgr.id
          and b["data"]["applicant"]["assigned_to"]["employee_code"] == "B5-mgr", (s, b))
    if not ok:
        return
    aid = b["data"]["applicant"]["id"]
    s, b, _ = post(C["mgr"], "recruitment/applicant/list/")
    check("view-only manager sees the applicant assigned to them", s == 200 and [x["id"] for x in b["data"]] == [aid], (s, b))
    s, b, _ = post(C["mgr"], "recruitment/applicant/list/", {"assigned_to_me": True})
    check("assigned_to_me filter works with employee assignment", s == 200 and len(b["data"]) == 1, (s, b))
    s, b, _ = post(C["hr"], "recruitment/applicant/list/", {"assigned_to_id": mgr.id})
    check("assigned_to_id list filter uses the employee id", s == 200 and len(b["data"]) == 1, (s, b))

    # ================= offer, email, resend
    post(C["hr"], "recruitment/applicant/status-update/", {"applicant_id": aid, "status": "SELECTED"})
    joining = timezone.localdate() + timedelta(days=20)
    valid = timezone.localdate() + timedelta(days=7)
    s, b, _ = post(C["hr"], "recruitment/applicant/verification/", {"applicant_id": aid, "offer": {
        "salary_structure_id": structure.id, "joining_date": str(joining), "monthly_gross": "40000",
        "probation_months": 6, "notice_period_days": 30, "valid_until": str(valid), "notes": "Laptop provided."}})
    off = b.get("data", {}).get("current_offer") or {}
    check("offer stores probation, notice period, valid_until", s == 200 and off.get("probation_months") == 6
          and off.get("notice_period_days") == 30 and off.get("valid_until") == str(valid), (s, b))
    s, b, _ = post(C["hr"], "recruitment/applicant/verification/", {"applicant_id": aid, "offer": {
        "salary_structure_id": structure.id, "joining_date": str(joining), "monthly_gross": "40000",
        "valid_until": str(timezone.localdate() - timedelta(days=1))}})
    check("valid_until in the past -> 400", s == 400, (s, b))

    s, b, r = post(C["hr"], "recruitment/applicant/offer-letter/download/", {"applicant_id": aid})
    check("HR downloads the offer letter PDF (draft)", s == 200 and r["Content-Type"] == "application/pdf"
          and r.content[:4] == b"%PDF", (s, r.get("Content-Type")))
    s, b, _ = post(C["plain"], "recruitment/applicant/offer-letter/download/", {"applicant_id": aid})
    check("download without permission -> 403", s == 403, s)

    mail.outbox = []
    s, b, _ = post(C["hr"], "recruitment/applicant/verification/", {
        "applicant_id": aid, "offer_action": "SEND", "email_message": "Please bring your PAN card on day one."})
    msg = mail.outbox[0] if mail.outbox else None
    check("SEND emails the candidate once", s == 200 and len(mail.outbox) == 1 and msg.to == ["priya@cand.test"], (s, b, len(mail.outbox)))
    if not msg:
        return
    html = msg.alternatives[0][0]
    link = re.search(r'href="(http[^"]+/recruitment/offer/([^"/]+)/)"', html)
    check("email has message, PDF attachment and the response link",
          "Please bring your PAN card" in html and link is not None and msg.attachments
          and msg.attachments[0][0].startswith("Offer_Letter_") and msg.attachments[0][1][:4] == b"%PDF"
          and msg.reply_to == ["hr@b5.test"], (msg.attachments and msg.attachments[0][0], link))
    token = link.group(2)
    offer = ApplicantOffer.objects.get(response_token=token)
    check("offer SENT, email_count 1", offer.status == "SENT" and offer.email_count == 1, (offer.status, offer.email_count))

    s, b, _ = post(C["hr"], "recruitment/applicant/verification/", {"applicant_id": aid, "offer_action": "SEND"})
    offer.refresh_from_db()
    check("resend while SENT: second email, same link", s == 200 and len(mail.outbox) == 2
          and token in mail.outbox[1].alternatives[0][0] and offer.email_count == 2, (s, len(mail.outbox), offer.email_count))
    s, b, _ = post(C["hr"], "recruitment/applicant/verification/", {"applicant_id": aid, "offer_action": "SEND", "send_email": False})
    check("send_email=false records nothing new and sends no mail", s == 200 and len(mail.outbox) == 2, (s, len(mail.outbox)))
    history = [h["action"] for h in b["data"]["history"]]
    check("each email is in the applicant history", history.count("OFFER_EMAILED") == 2, history)

    # ================= public page (candidate)
    browser = BrowserClient()
    r = browser.get(f"/recruitment/offer/{token}/")
    page = r.content.decode()
    check("public page opens without login and shows the offer + buttons",
          r.status_code == 200 and "Accept offer" in page and "Decline offer" in page and "40,000.00" in page, r.status_code)
    r = browser.get(f"/recruitment/offer/{token}/letter/")
    check("public PDF link works", r.status_code == 200 and r.content[:4] == b"%PDF", r.status_code)
    r = browser.get("/recruitment/offer/not-a-real-token/")
    check("unknown token -> 404 page", r.status_code == 404 and "not valid" in r.content.decode(), r.status_code)

    with mock.patch("app.communications.notification_service.notify") as fake_notify:
        with TestCase.captureOnCommitCallbacks(execute=True):
            r = browser.post(f"/recruitment/offer/{token}/", {"action": "ACCEPT", "note": "Happy to join!"})
    offer.refresh_from_db()
    check("candidate accepts: offer ACCEPTED via CANDIDATE with note", r.status_code == 200 and offer.status == "ACCEPTED"
          and offer.responded_via == "CANDIDATE" and offer.response_note == "Happy to join!", (r.status_code, offer.status))
    check("thank-you page shown, no buttons", "You have accepted the offer" in r.content.decode()
          and "Accept offer" not in r.content.decode())
    notified = {u.id for u in fake_notify.call_args.kwargs["users"]} if fake_notify.called else set()
    check("HR is notified (creator, assigned employee, verification.update holders, owner)",
          {hr.user_id, mgr.user_id, owner.id} <= notified, notified)
    s, b, _ = post(C["hr"], "recruitment/applicant/detail/", {"applicant_id": aid})
    acc = next(c for c in b["data"]["verification_checks"] if c["key"] == "OFFER_ACCEPTANCE")
    check("OFFER_ACCEPTANCE check done after candidate accepts", acc["status"] == "DONE", acc)

    r = browser.post(f"/recruitment/offer/{token}/", {"action": "DECLINE"})
    offer.refresh_from_db()
    check("answer is final: second answer -> 400, still ACCEPTED",
          r.status_code == 400 and "already accepted" in r.content.decode() and offer.status == "ACCEPTED", r.status_code)
    s, b, _ = post(C["hr"], "recruitment/applicant/verification/", {"applicant_id": aid, "offer_action": "DECLINE"})
    check("HR cannot change an accepted offer either", s == 400, (s, b))
    r = browser.get(f"/recruitment/offer/{token}/")
    check("link afterwards shows the recorded answer", r.status_code == 200 and "You accepted this offer" in r.content.decode())

    # ================= expired, superseded, HR on behalf
    base2 = {**base, "email": "amit@cand.test", "mobile": "9811100002", "first_name": "Amit"}
    s, b, _ = post(C["hr"], "recruitment/applicant/create/", base2)
    bid = b["data"]["applicant"]["id"]
    post(C["hr"], "recruitment/applicant/status-update/", {"applicant_id": bid, "status": "SELECTED"})
    post(C["hr"], "recruitment/applicant/verification/", {"applicant_id": bid, "offer": {
        "salary_structure_id": structure.id, "joining_date": str(joining), "annual_ctc": "480000", "valid_until": str(valid)}})
    post(C["hr"], "recruitment/applicant/verification/", {"applicant_id": bid, "offer_action": "SEND"})
    o1 = ApplicantOffer.objects.get(applicant_id=bid, version=1)
    ApplicantOffer.objects.filter(pk=o1.pk).update(valid_until=timezone.localdate() - timedelta(days=1))
    r = browser.get(f"/recruitment/offer/{o1.response_token}/")
    check("expired offer page", "expired" in r.content.decode() and "Accept offer" not in r.content.decode())
    r = browser.post(f"/recruitment/offer/{o1.response_token}/", {"action": "ACCEPT"})
    check("expired offer cannot be accepted by the candidate", r.status_code == 400)
    ApplicantOffer.objects.filter(pk=o1.pk).update(valid_until=valid)
    post(C["hr"], "recruitment/applicant/verification/", {"applicant_id": bid, "offer": {
        "salary_structure_id": structure.id, "joining_date": str(joining), "annual_ctc": "500000"}})
    r = browser.get(f"/recruitment/offer/{o1.response_token}/")
    check("old link after a revised offer -> no longer available", "no longer available" in r.content.decode()
          and "Accept offer" not in r.content.decode())
    s, b, _ = post(C["hr"], "recruitment/applicant/verification/", {"applicant_id": bid, "offer_action": "DECLINE",
                                                                    "offer_note": "Candidate called to decline"})
    o2 = ApplicantOffer.objects.get(applicant_id=bid, version=2)
    check("HR can still record an answer on behalf of the candidate", s == 200 and o2.status == "DECLINED"
          and o2.responded_via == "HR", (s, o2.status, o2.responded_via))


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
