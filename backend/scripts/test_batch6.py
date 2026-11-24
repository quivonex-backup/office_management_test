"""
Batch 6 checks: helpdesk (tickets), assets, visitors, employee deactivate
(login off + assets_held info).

Run after makemigrations + migrate; any database; everything is rolled back:
    python manage.py shell -c "exec(open('scripts/test_batch6.py').read())"
"""
import sys
import traceback
from datetime import timedelta
from unittest import mock

from django.db import transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from app.accounts.models import AccessRole, Branch, Organization, OrganizationMembership, Permission, Role, User
from app.accounts.services import seed_organization_defaults
from app.assets.models import Asset
from app.employees.models import Department, Employee
from app.helpdesk.models import Ticket
from app.visitors.models import Visit

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


class Notified:
    """Collects notify() calls made through transaction.on_commit."""

    def __init__(self):
        self.calls = []

    def __call__(self, users=None, event_code=None, **kw):
        users = users if isinstance(users, (list, tuple)) else [users]
        self.calls.append((event_code, {u.id for u in users if u is not None}))

    def users_for(self, event):
        out = set()
        for code, ids in self.calls:
            if code == event:
                out |= ids
        return out


def run():
    admin_role, _ = Role.objects.get_or_create(name="Admin", defaults={"is_active": True})
    emp_role, _ = Role.objects.get_or_create(name="Employee", defaults={"is_active": True})
    n = [0]

    def user(name, role=emp_role):
        n[0] += 1
        u = User.objects.create(username=f"b6_{name}", email=f"b6_{name}@x.test", mobile=f"60000000{n[0]:02d}", role=role)
        u.set_password("x-test-123")
        u.save()
        return u

    owner = user("owner", admin_role)
    org = Organization.objects.create(organization_name="B6 Org", owner=owner, email="hr@b6.test")
    OrganizationMembership.objects.create(organization=org, user=owner, is_active=True)
    seed_organization_defaults(org)
    roles = {r.name: r for r in AccessRole.objects.filter(organization=org)}
    it_dept = Department.objects.create(organization=org, name="IT")
    hr_dept = Department.objects.create(organization=org, name="HR")
    branch = Branch.objects.create(organization=org, name="Pune")

    viewer = AccessRole.objects.create(organization=org, name="Asset viewer")
    viewer.permissions.add(Permission.objects.get(code="asset.view"))
    it_role = AccessRole.objects.create(organization=org, name="IT Support")
    it_role.permissions.add(Permission.objects.get(code="ticket.handle"))

    def employee(name, role=None, dept=None):
        u = user(name)
        OrganizationMembership.objects.create(organization=org, user=u, is_active=True)
        return Employee.objects.create(organization=org, first_name=name.title(), last_name="T",
                                       employee_code=f"B6-{name}", user=u, access_role=role,
                                       department_ref=dept, employment_status="ACTIVE")

    hr = employee("hrmgr", roles["HR Manager"], hr_dept)
    front = employee("front", roles["HR Executive"], hr_dept)
    it1 = employee("ithandler", it_role, it_dept)
    it2 = employee("itother", None, it_dept)
    staff = employee("staff")
    other = employee("other")
    view = employee("viewer", viewer)
    C = {e.employee_code.split("-")[1]: client_for(e.user) for e in (hr, front, it1, it2, staff, other, view)}
    C["owner"] = client_for(owner)

    # ---- permissions seeded
    hr_codes = set(roles["HR Manager"].permissions.values_list("code", flat=True))
    check("new codes in catalog + HR Manager defaults",
          {"ticket.manage", "asset.manage", "visitor.manage"} <= hr_codes
          and Permission.objects.filter(code__in=["ticket.handle", "asset.view"]).count() == 2, hr_codes)

    # ================= HELPDESK
    s, b = post(C["staff"], "helpdesk/category/create/", {"name": "IT"})
    check("plain employee cannot create categories", s == 403, s)
    s, b = post(C["owner"], "helpdesk/category/create/", {"name": "IT support", "department_id": it_dept.id})
    check("category created with handling department", s == 201 and b["data"]["department"]["id"] == it_dept.id, (s, b))
    it_cat = b["data"]["id"]
    s, b = post(C["owner"], "helpdesk/category/create/", {"name": "it SUPPORT"})
    check("duplicate category name (case-insensitive) -> 400", s == 400, s)
    s, b = post(C["owner"], "helpdesk/category/create/", {"name": "Payroll", "department_id": hr_dept.id,
                                                          "default_assignee_id": hr.id})
    pay_cat = b["data"]["id"]
    s, b = post(C["staff"], "helpdesk/category/options/")
    check("employee sees active categories for the form", s == 200 and len(b["data"]) == 2, (s, b))

    notified = Notified()
    with mock.patch("app.communications.notification_service.notify", notified):
        with TestCase.captureOnCommitCallbacks(execute=True):
            s, b = post(C["staff"], "helpdesk/ticket/create/", {
                "category_id": it_cat, "subject": "Laptop not starting", "description": "Black screen",
                "priority": "HIGH"})
    ok = s == 201
    check("employee raises a ticket (OPEN, TKT- code)", ok and b["data"]["ticket"]["status"] == "OPEN"
          and b["data"]["ticket"]["ticket_code"].startswith("TKT-"), (s, b))
    if not ok:
        return
    tid = b["data"]["ticket"]["id"]
    check("raiser roles + actions (can close, cannot assign)",
          b["data"]["my_roles"] == ["RAISER"] and b["data"]["allowed_actions"]["status_moves"] == ["CLOSED"]
          and not b["data"]["allowed_actions"]["assign"], b["data"])
    check("new ticket notifies the department's handlers (ticket.handle)",
          notified.users_for("TICKET_CREATED") == {it1.user_id}, notified.calls)

    s, _ = post(C["itother"], "helpdesk/ticket/list/")
    check("same department without ticket.handle -> no list (403)", s == 403, s)
    s, b = post(C["ithandler"], "helpdesk/ticket/list/")
    check("handler lists own department's tickets + summary", s == 200 and [t["id"] for t in b["data"]] == [tid]
          and b["summary"]["by_status"]["OPEN"] == 1 and b["summary"]["unassigned_open"] == 1, (s, b))
    s, b = post(C["hrmgr"], "helpdesk/ticket/list/")
    check("ticket.manage sees every ticket", s == 200 and len(b["data"]) == 1, (s, b))
    today = str(timezone.localdate())
    s, b = post(C["hrmgr"], "helpdesk/ticket/list/", {"from_date": today, "to_date": today})
    s2, b2 = post(C["hrmgr"], "helpdesk/ticket/list/", {"from_date": "2026-01-01", "to_date": "2026-01-02"})
    s3, _ = post(C["hrmgr"], "helpdesk/ticket/list/", {"from_date": "24-11-2026"})
    check("ticket list date range (today 1, old range 0, bad format 400)",
          s == 200 and len(b["data"]) == 1 and s2 == 200 and len(b2["data"]) == 0 and s3 == 400, (s, s2, s3))
    s, _ = post(C["staff"], "helpdesk/ticket/list/")
    check("raiser cannot use the handling list (403)", s == 403, s)
    s, b = post(C["staff"], "helpdesk/ticket/my-tickets/")
    check("my-tickets shows what I raised", s == 200 and len(b["data"]) == 1, (s, b))
    s, _ = post(C["other"], "helpdesk/ticket/detail/", {"ticket_id": tid})
    check("unrelated employee -> 404", s == 404, s)

    s, b = post(C["ithandler"], "helpdesk/ticket/assign/", {"ticket_id": tid, "assignee_id": staff.id})
    check("handler cannot assign outside the category's department", s == 400, (s, b))
    notified = Notified()
    with mock.patch("app.communications.notification_service.notify", notified):
        with TestCase.captureOnCommitCallbacks(execute=True):
            s, b = post(C["ithandler"], "helpdesk/ticket/assign/", {"ticket_id": tid, "assignee_id": it2.id})
    check("handler assigns to a department colleague (+ notified)",
          s == 200 and b["data"]["ticket"]["assigned_to"]["id"] == it2.id
          and notified.users_for("TICKET_ASSIGNED") == {it2.user_id}, (s, b))
    s, b = post(C["itother"], "helpdesk/ticket/detail/", {"ticket_id": tid})
    check("assignee (no code) can open the ticket", s == 200 and "HANDLER" in b["data"]["my_roles"], (s, b))
    s, b = post(C["itother"], "helpdesk/ticket/my-tickets/", {"view": "assigned"})
    check("my-tickets view=assigned", s == 200 and len(b["data"]) == 1, (s, b))

    notified = Notified()
    with mock.patch("app.communications.notification_service.notify", notified):
        with TestCase.captureOnCommitCallbacks(execute=True):
            s, b = post(C["staff"], "helpdesk/ticket/comment/", {"ticket_id": tid, "message": "Any update?"})
    check("raiser reply notifies the assignee", s == 201 and notified.users_for("TICKET_REPLY") == {it2.user_id},
          (s, notified.calls))
    s, b = post(C["staff"], "helpdesk/ticket/comment/", {"ticket_id": tid, "message": "x", "is_internal": True})
    check("raiser cannot add internal notes", s == 400, (s, b))
    s, b = post(C["itother"], "helpdesk/ticket/comment/", {"ticket_id": tid, "message": "Ordering a new battery",
                                                           "is_internal": True})
    check("handler adds an internal note", s == 201 and any(c["is_internal"] for c in b["data"]["comments"]), (s, b))
    s, b = post(C["staff"], "helpdesk/ticket/detail/", {"ticket_id": tid})
    check("internal notes hidden from the raiser", s == 200 and not any(c["is_internal"] for c in b["data"]["comments"])
          and any(c["is_system"] for c in b["data"]["comments"]), b.get("data", {}).get("comments"))

    s, b = post(C["staff"], "helpdesk/ticket/status-update/", {"ticket_id": tid, "status": "IN_PROGRESS"})
    check("raiser cannot move to IN_PROGRESS", s == 400 and "Cannot change status" in b["message"], (s, b))
    post(C["itother"], "helpdesk/ticket/status-update/", {"ticket_id": tid, "status": "IN_PROGRESS"})
    notified = Notified()
    with mock.patch("app.communications.notification_service.notify", notified):
        with TestCase.captureOnCommitCallbacks(execute=True):
            s, b = post(C["itother"], "helpdesk/ticket/status-update/", {"ticket_id": tid, "status": "RESOLVED",
                                                                         "note": "Battery replaced"})
    t = Ticket.objects.get(pk=tid)
    check("handler resolves (resolved_at set, raiser notified)", s == 200 and t.status == "RESOLVED"
          and t.resolved_at and notified.users_for("TICKET_STATUS") == {staff.user_id}, (s, b))
    s, b = post(C["staff"], "helpdesk/ticket/status-update/", {"ticket_id": tid, "status": "OPEN", "note": "Still broken"})
    t.refresh_from_db()
    check("raiser reopens a resolved ticket", s == 200 and t.status == "OPEN" and t.resolved_at is None, (s, b))
    post(C["itother"], "helpdesk/ticket/status-update/", {"ticket_id": tid, "status": "RESOLVED"})
    s, b = post(C["staff"], "helpdesk/ticket/status-update/", {"ticket_id": tid, "status": "CLOSED"})
    t.refresh_from_db()
    check("raiser confirms -> CLOSED (closed_at)", s == 200 and t.status == "CLOSED" and t.closed_at, (s, b))
    s, b = post(C["itother"], "helpdesk/ticket/status-update/", {"ticket_id": tid, "status": "IN_PROGRESS"})
    s2, _ = post(C["staff"], "helpdesk/ticket/comment/", {"ticket_id": tid, "message": "thanks"})
    check("closed is final: no status change, no comments", s == 400 and s2 == 400, (s, s2))

    with mock.patch("app.communications.notification_service.notify", Notified()):
        with TestCase.captureOnCommitCallbacks(execute=True):
            s, b = post(C["staff"], "helpdesk/ticket/create/", {
                "category_id": pay_cat, "subject": "Payslip wrong", "description": "Missing overtime"})
    pid = b["data"]["ticket"]["id"]
    check("category default assignee picks up new tickets", s == 201
          and b["data"]["ticket"]["assigned_to"]["id"] == hr.id, (s, b))
    s, b = post(C["ithandler"], "helpdesk/ticket/detail/", {"ticket_id": pid})
    check("IT handler cannot see HR / payroll tickets", s == 404, s)
    s, b = post(C["hrmgr"], "helpdesk/ticket/update/", {"ticket_id": pid, "priority": "URGENT", "category_id": it_cat})
    check("update priority + category (system line added)", s == 200 and b["data"]["ticket"]["priority"] == "URGENT"
          and b["data"]["ticket"]["category"]["id"] == it_cat
          and any("Priority changed" in c["message"] for c in b["data"]["comments"]), (s, b))
    s, b = post(C["staff"], "helpdesk/ticket/create/", {"category_id": it_cat, "subject": "x", "description": "y",
                                                        "raised_by_id": other.id})
    check("raising for someone else needs ticket.manage", s == 403, s)
    with mock.patch("app.communications.notification_service.notify", Notified()):
        s, b = post(C["hrmgr"], "helpdesk/ticket/create/", {"category_id": it_cat, "subject": "Access card",
                                                            "description": "Lost card", "raised_by_id": other.id})
    check("manager raises for an employee", s == 201 and b["data"]["ticket"]["raised_by"]["id"] == other.id, (s, b))
    post(C["owner"], "helpdesk/category/deactivate/", {"category_id": pay_cat})
    s, b = post(C["staff"], "helpdesk/ticket/create/", {"category_id": pay_cat, "subject": "x", "description": "y"})
    s2, b2 = post(C["staff"], "helpdesk/category/options/")
    check("deactivated category: not offered, cannot be used", s == 400 and len(b2["data"]) == 1, (s, b2))

    # ================= ASSETS
    s, _ = post(C["staff"], "assets/category/create/", {"name": "Laptop"})
    check("plain employee cannot manage assets", s == 403, s)
    s, b = post(C["hrmgr"], "assets/category/create/", {"name": "Laptop"})
    cat = b["data"]["id"]
    base = {"category_id": cat, "name": "Dell Latitude 5440", "brand": "Dell", "serial_number": "SN-123",
            "purchase_date": "2026-01-10", "purchase_cost": "72000", "warranty_until": "2029-01-09",
            "branch_id": branch.id}
    s, b = post(C["hrmgr"], "assets/asset/create/", base)
    ok = s == 201
    check("asset created (AST- code, AVAILABLE)", ok and b["data"]["asset"]["asset_code"].startswith("AST-")
          and b["data"]["asset"]["status"] == "AVAILABLE", (s, b))
    if not ok:
        return
    aid = b["data"]["asset"]["id"]
    s, b = post(C["hrmgr"], "assets/asset/create/", {**base, "serial_number": "sn-123"})
    check("duplicate serial number -> 400", s == 400 and "serial_number" in b["errors"], (s, b))
    s, b = post(C["hrmgr"], "assets/asset/create/", {**base, "serial_number": "SN-9", "warranty_until": "2025-01-01"})
    check("warranty before purchase -> 400", s == 400, (s, b))

    notified = Notified()
    with mock.patch("app.communications.notification_service.notify", notified):
        with TestCase.captureOnCommitCallbacks(execute=True):
            s, b = post(C["hrmgr"], "assets/asset/assign/", {"asset_id": aid, "employee_id": staff.id,
                                                             "condition": "NEW", "note": "With charger"})
    check("assign: ASSIGNED, holder set, history row, employee notified",
          s == 200 and b["data"]["asset"]["status"] == "ASSIGNED"
          and b["data"]["asset"]["current_holder"]["id"] == staff.id and len(b["data"]["assignments"]) == 1
          and notified.users_for("ASSET_ASSIGNED") == {staff.user_id}, (s, b))
    s, b = post(C["hrmgr"], "assets/asset/assign/", {"asset_id": aid, "employee_id": other.id})
    check("cannot assign an assigned asset", s == 400, (s, b))
    s, b = post(C["staff"], "assets/asset/my-assets/")
    check("employee sees own assets (no cost)", s == 200 and len(b["data"]) == 1 and "purchase_cost" not in b["data"][0]
          and b["data"][0]["assigned_on"], (s, b))
    s, _ = post(C["staff"], "assets/asset/list/")
    s2, b2 = post(C["viewer"], "assets/asset/list/", {"holder_id": staff.id})
    s3, _ = post(C["viewer"], "assets/asset/create/", {**base, "serial_number": "SN-2"})
    check("asset.view: list (holder filter + summary) but no create",
          s == 403 and s2 == 200 and len(b2["data"]) == 1 and b2["summary"]["by_status"]["ASSIGNED"] == 1 and s3 == 403,
          (s, s2, s3))
    s, b = post(C["hrmgr"], "assets/asset/update/", {"asset_id": aid, "status": "IN_REPAIR"})
    check("status change while assigned -> 400", s == 400, (s, b))

    # employee deactivate: not blocked, assets reported, login off
    s, b = post(C["owner"], "employees/deactivate/", {"employee_id": staff.id,
                                                      "last_working_day": str(timezone.localdate())})
    staff.user.refresh_from_db()
    member = OrganizationMembership.objects.get(organization=org, user=staff.user)
    check("deactivate not blocked; assets_held listed", s == 200
          and [a["id"] for a in b["data"]["assets_held"]] == [aid], (s, b))
    check("deactivate turns login off (membership + user)", b["data"].get("login_disabled") is True
          and not member.is_active and not staff.user.is_active, (b.get("data"), member.is_active))
    owner.refresh_from_db()
    check("owner untouched", owner.is_active)

    # reactivate (rehire)
    s, b = post(C["owner"], "employees/list/", {"inactive_only": True})
    check("employees/list inactive_only shows people who left", s == 200
          and staff.id in [e["id"] for e in b["data"]], (s, b.get("message")))
    s, _ = post(C["other"], "employees/reactivate/", {"employee_id": staff.id})
    check("reactivate needs employee.update", s == 403, s)
    s, b = post(C["owner"], "employees/reactivate/", {"employee_id": staff.id, "joining_date": "2026-12-01"})
    staff.refresh_from_db()
    staff.user.refresh_from_db()
    member.refresh_from_db()
    check("reactivate: employee ACTIVE, new joining date, membership + login back on",
          s == 200 and b["data"]["login_enabled"] and staff.is_active and staff.employment_status == "ACTIVE"
          and str(staff.joining_date) == "2026-12-01" and member.is_active and staff.user.is_active, (s, b))
    s, b = post(C["staff"], "employees/my-profile/")
    check("same login works again after reactivation", s == 200, (s, b.get("message")))
    s, _ = post(C["owner"], "employees/reactivate/", {"employee_id": staff.id})
    check("reactivating an active employee -> 404", s == 404, s)

    s, b = post(C["hrmgr"], "assets/asset/return/", {"asset_id": aid, "condition": "DAMAGED",
                                                     "status_after": "IN_REPAIR", "note": "Hinge broken"})
    row = b["data"]["assignments"][0] if s == 200 else {}
    check("return: history closed, holder cleared, status_after applied", s == 200
          and b["data"]["asset"]["status"] == "IN_REPAIR" and b["data"]["asset"]["current_holder"] is None
          and row.get("returned_on") and row.get("condition_on_return") == "DAMAGED", (s, b))
    s, _ = post(C["hrmgr"], "assets/asset/assign/", {"asset_id": aid, "employee_id": other.id})
    check("in-repair asset cannot be assigned", s == 400, s)
    post(C["hrmgr"], "assets/asset/update/", {"asset_id": aid, "status": "AVAILABLE"})
    post(C["hrmgr"], "assets/asset/assign/", {"asset_id": aid, "employee_id": other.id})
    s, _ = post(C["hrmgr"], "assets/asset/deactivate/", {"asset_id": aid})
    post(C["hrmgr"], "assets/asset/return/", {"asset_id": aid})
    s2, _ = post(C["hrmgr"], "assets/asset/deactivate/", {"asset_id": aid})
    s3, b3 = post(C["hrmgr"], "assets/asset/detail/", {"asset_id": aid})
    check("remove: refused while assigned, allowed after return", s == 400 and s2 == 200 and s3 == 404, (s, s2, s3))
    check("full holder history kept", Asset.objects.get(pk=aid).assignments.count() == 2)

    # ================= VISITORS
    visit = {"visitor_name": "Ravi Kumar", "visitor_mobile": "9876500011", "purpose": "MEETING",
             "visitor_company": "ABC Tech", "host_id": it1.id, "branch_id": branch.id}
    s, _ = post(C["other"], "visitors/visit/create/", visit)
    check("visitor log needs visitor.manage", s == 403, s)
    notified = Notified()
    with mock.patch("app.communications.notification_service.notify", notified):
        with TestCase.captureOnCommitCallbacks(execute=True):
            s, b = post(C["front"], "visitors/visit/create/", visit)
    ok = s == 201
    check("front desk adds a visit (checked in now, inside, host notified)",
          ok and b["data"]["visit_code"].startswith("VIS-") and b["data"]["check_in_at"] and b["data"]["is_inside"]
          and notified.users_for("VISITOR_ARRIVED") == {it1.user_id}, (s, b))
    if not ok:
        return
    v1 = b["data"]["id"]
    s, b = post(C["front"], "visitors/visit/create/", {"visitor_name": "Courier", "visitor_mobile": "98-76",
                                                       "purpose": "DELIVERY"})
    check("invalid mobile -> 400", s == 400 and "visitor_mobile" in b["errors"], (s, b))
    s, b = post(C["front"], "visitors/visit/create/", {**visit, "id_proof_type": "AADHAAR", "id_proof_last4": "123456789012"})
    check("full ID number refused (last 4 only)", s == 400 and "id_proof_last4" in b["errors"], (s, b))
    with mock.patch("app.communications.notification_service.notify", Notified()):
        s, b = post(C["front"], "visitors/visit/create/", {"visitor_name": "Ravi Kumar", "visitor_mobile": "9876500011",
                                                           "purpose": "CLIENT", "id_proof_type": "AADHAAR",
                                                           "id_proof_last4": "9012"})
    check("same visitor can come again (new row)", s == 201, (s, b))
    v2 = b["data"]["id"]
    s, b = post(C["front"], "visitors/visit/lookup/", {"visitor_mobile": "9876500011"})
    check("lookup by mobile autofills name / company + count",
          s == 200 and b["data"]["found"] and b["data"]["visit_count"] == 2
          and b["data"]["visitor_name"] == "Ravi Kumar" and b["data"]["visitor_company"] == "ABC Tech", (s, b))
    s, b = post(C["front"], "visitors/visit/lookup/", {"visitor_mobile": "9000000000"})
    check("lookup unknown mobile -> found false", s == 200 and b["data"]["found"] is False, (s, b))
    s, b = post(C["front"], "visitors/visit/list/")
    check("list defaults to today", s == 200 and len(b["data"]) == 2, (s, b))
    s, b = post(C["front"], "visitors/visit/check-out/", {"visit_id": v1})
    s2, b2 = post(C["front"], "visitors/visit/list/", {"inside_only": True})
    s3, _ = post(C["front"], "visitors/visit/check-out/", {"visit_id": v1})
    check("check-out; inside_only shows who is still in; second check-out -> 400",
          s == 200 and b["data"]["is_inside"] is False and [v["id"] for v in b2["data"]] == [v2] and s3 == 400,
          (s, b2, s3))
    past = (timezone.now() - timedelta(days=2)).isoformat()
    s, b = post(C["front"], "visitors/visit/update/", {"visit_id": v1, "check_out_at": past})
    check("check-out before check-in -> 400", s == 400, (s, b))
    s, b = post(C["front"], "visitors/visit/update/", {"visit_id": v2, "badge_number": "B-12", "host_id": None})
    check("update badge, clear host", s == 200 and b["data"]["badge_number"] == "B-12" and b["data"]["host"] is None, (s, b))
    s, b = post(C["front"], "visitors/visit/list/", {"search": "ABC", "purpose": "MEETING"})
    check("search + purpose filter", s == 200 and [v["id"] for v in b["data"]] == [v1], (s, b))
    s, b = post(C["ithandler"], "visitors/visit/my-visitors/")
    check("host sees own visitors (no ID / photo fields)", s == 200 and [v["id"] for v in b["data"]] == [v1]
          and "id_proof_last4" not in b["data"][0], (s, b))
    s, b = post(C["front"], "visitors/visit/list/", {"from_date": "2026-12-31", "to_date": "2026-01-01"})
    check("from_date after to_date -> 400", s == 400, (s, b))
    post(C["front"], "visitors/visit/deactivate/", {"visit_id": v2})
    s, b = post(C["front"], "visitors/visit/list/")
    check("removed visit leaves the list", s == 200 and len(b["data"]) == 1 and Visit.objects.get(pk=v2).is_active is False)


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
