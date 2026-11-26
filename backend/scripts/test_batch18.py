"""
Batch 18 checks: reports/assets/ and reports/visitors/.

Run after migrate; any database; everything is rolled back:
    python manage.py shell -c "exec(open('scripts/test_batch18.py').read())"
"""
import sys
import traceback
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from app.accounts.models import AccessRole, Organization, OrganizationMembership, Role, User
from app.accounts.services import seed_organization_defaults
from app.assets.models import Asset, AssetAssignment, AssetCategory
from app.employees.models import Employee
from app.visitors.models import Visit

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


def post(c, url, data=None):
    r = c.post("/" + url, data or {}, format="json")
    if r.get("Content-Type", "").startswith("application/vnd.openxmlformats"):
        return r.status_code, {"xlsx": True, "bytes": len(r.content)}
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.content[:200]}


def run():
    admin_role, _ = Role.objects.get_or_create(name="Admin", defaults={"is_active": True})
    emp_role, _ = Role.objects.get_or_create(name="Employee", defaults={"is_active": True})
    n = [0]

    def user(name, role=emp_role):
        n[0] += 1
        return User.objects.create(username=f"b18_{name}", email=f"b18_{name}@x.test", mobile=f"18000000{n[0]:02d}",
                                   role=role, first_name=name.title())

    owner = user("owner", admin_role)
    org = Organization.objects.create(organization_name="B18 Org", owner=owner)
    OrganizationMembership.objects.create(organization=org, user=owner, is_active=True)
    seed_organization_defaults(org)
    roles = {r.name: r for r in AccessRole.objects.filter(organization=org)}

    def employee(name, role=None):
        u = user(name)
        OrganizationMembership.objects.create(organization=org, user=u, is_active=True)
        return Employee.objects.create(organization=org, first_name=name.title(), last_name="T",
                                       employee_code=f"B18-{name}", user=u, access_role=role,
                                       employment_status="ACTIVE", joining_date=date(2025, 1, 1))

    hr = employee("hr", roles["HR Manager"])            # asset.manage + visitor.manage
    pay = employee("pay", roles["Payroll Manager"])     # asset.view, no visitor.manage
    dev = employee("dev")
    qa = employee("qa")
    C = {"owner": client_for(owner), "hr": client_for(hr.user), "pay": client_for(pay.user),
         "dev": client_for(dev.user)}
    today = timezone.localdate()

    # ================= LIST
    s, b = post(C["owner"], "reports/list/")
    keys = {r["key"] for r in b["data"]["reports"]}
    check("owner: 11 reports incl. assets + visitors", len(keys) == 11 and {"assets", "visitors"} <= keys, keys)
    s, b = post(C["pay"], "reports/list/")
    keys = {r["key"] for r in b["data"]["reports"]}
    check("Payroll Manager (asset.view): assets yes, visitors no", "assets" in keys and "visitors" not in keys, keys)
    s, b = post(C["dev"], "reports/assets/")
    check("plain employee -> 403 assets", s == 403, s)
    s, b = post(C["pay"], "reports/visitors/")
    check("no visitor.manage -> 403 visitors", s == 403, s)

    # ================= ASSETS data
    laptops = AssetCategory.objects.create(organization=org, name="Laptops")
    phones = AssetCategory.objects.create(organization=org, name="Phones")

    def asset(code, cat, status="AVAILABLE", holder=None, cost=None, warranty=None):
        return Asset.objects.create(organization=org, asset_code=code, category=cat, name=f"Item {code}",
                                    status=status, current_holder=holder, purchase_cost=cost,
                                    warranty_until=warranty, serial_number=f"SN-{code}")

    a1 = asset("B18A1", laptops, "ASSIGNED", dev, D("60000"), today + timedelta(days=10))
    a2 = asset("B18A2", laptops, "ASSIGNED", dev, D("55000"), today - timedelta(days=5))
    a3 = asset("B18A3", phones, "ASSIGNED", qa, D("20000"))
    asset("B18A4", phones, "AVAILABLE", None, D("15000"))
    asset("B18A5", laptops, "IN_REPAIR")
    gone = asset("B18A6", laptops, "RETIRED")
    Asset.objects.filter(pk=gone.pk).update(is_active=False)
    m_start = today.replace(day=1)
    AssetAssignment.objects.create(asset=a1, employee=dev, assigned_on=m_start, condition_on_issue="NEW")
    AssetAssignment.objects.create(asset=a2, employee=dev, assigned_on=m_start - timedelta(days=60))
    AssetAssignment.objects.create(asset=a3, employee=qa, assigned_on=m_start - timedelta(days=30))
    AssetAssignment.objects.create(asset=a3, employee=dev, assigned_on=m_start - timedelta(days=90),
                                   returned_on=m_start, condition_on_return="GOOD")

    s, b = post(C["pay"], "reports/assets/")
    d = b.get("data") or {}
    check("register: 5 active assets, deactivated excluded", s == 200 and d["report"] == "assets"
          and d["pagination"]["total_rows"] == 5, b)
    check("register summary + chart by status", d["summary"]["assigned"] == 3 and d["summary"]["available"] == 1
          and d["summary"]["in_repair"] == 1 and d["summary"]["warranty_expired"] == 1
          and d["chart"]["type"] == "bar", d.get("summary"))
    check("register totals purchase cost 150000", d["totals"].get("purchase_cost") == 150000.0, d.get("totals"))
    row = next(r for r in d["rows"] if r["asset_code"] == "B18A1")
    check("register row: holder + assigned_on from open assignment", row["holder"] == "Dev T"
          and row["assigned_on"] == str(m_start), row)
    check("branch column hidden (no branches)", "branch" not in {c["key"] for c in d["columns"]}, d["columns"])
    s, b = post(C["pay"], "reports/assets/", {"status": "ASSIGNED", "category_id": laptops.id})
    check("filter status + category", s == 200 and {r["asset_code"] for r in b["data"]["rows"]} == {"B18A1", "B18A2"}, b)
    s, b = post(C["pay"], "reports/assets/", {"warranty_expiring_days": 30})
    check("warranty expiring within 30 days", s == 200 and [r["asset_code"] for r in b["data"]["rows"]] == ["B18A1"], b)
    s, b = post(C["pay"], "reports/assets/", {"status": "BROKEN"})
    check("bad status -> 400", s == 400, b)

    s, b = post(C["hr"], "reports/assets/", {"view": "holders"})
    rows = {r["employee_code"]: r for r in b["data"]["rows"]}
    check("holders: dev 2 (115000), qa 1", s == 200 and rows["B18-dev"]["assets_held"] == 2
          and rows["B18-dev"]["value"] == 115000.0 and rows["B18-qa"]["assets_held"] == 1
          and b["data"]["totals"]["assets_held"] == 3, b)

    s, b = post(C["hr"], "reports/assets/", {"view": "history"})
    d = b["data"]
    check("history this month: a1 issued + a3 returned", s == 200 and d["summary"]["issued"] == 1
          and d["summary"]["returned"] == 1 and len(d["rows"]) == 2, d.get("summary"))
    s, b = post(C["hr"], "reports/assets/", {"view": "history", "employee_id": qa.id})
    check("history employee filter (qa issued last month -> none)", s == 200 and b["data"]["rows"] == [], b)
    s, b = post(C["hr"], "reports/assets/", {"format": "xlsx"})
    check("assets xlsx download", s == 200 and b.get("xlsx"), b)

    # ================= VISITORS data
    def aware(day, hh, mm=0):
        return timezone.make_aware(datetime.combine(day, time(hh, mm)))

    d1 = m_start
    d2 = min(m_start + timedelta(days=1), today)
    Visit.objects.create(organization=org, visit_code="B18V1", visitor_name="Ravi", visitor_mobile="9000000001",
                         visitor_company="Acme", visitor_count=2, purpose="CLIENT", host=dev,
                         check_in_at=aware(d1, 10), check_out_at=aware(d1, 11, 30))
    Visit.objects.create(organization=org, visit_code="B18V2", visitor_name="Sita", visitor_mobile="9000000002",
                         purpose="INTERVIEW", host=hr, check_in_at=aware(d2, 9), check_out_at=aware(d2, 9, 30))
    Visit.objects.create(organization=org, visit_code="B18V3", visitor_name="Courier", visitor_mobile="9000000003",
                         purpose="DELIVERY", check_in_at=aware(d2, 12))                 # still inside
    Visit.objects.create(organization=org, visit_code="B18V4", visitor_name="Old", visitor_mobile="9000000004",
                         purpose="MEETING", host=dev, check_in_at=aware(m_start - timedelta(days=3), 10))
    hidden = Visit.objects.create(organization=org, visit_code="B18V5", visitor_name="Deleted",
                                  visitor_mobile="9000000005", purpose="OTHER", check_in_at=aware(d1, 15))
    Visit.objects.filter(pk=hidden.pk).update(is_active=False)

    s, b = post(C["hr"], "reports/visitors/")
    d = b.get("data") or {}
    check("visit log this month: 3 visits (old + inactive excluded)", s == 200 and d["pagination"]["total_rows"] == 3, b)
    check("visit summary: visitors 4, still inside 1, avg stay 60", d["summary"]["visitors"] == 4
          and d["summary"]["still_inside"] == 1 and d["summary"]["average_minutes"] == 60, d.get("summary"))
    row = next(r for r in d["rows"] if r["visit_code"] == "B18V1")
    check("visit row: times + stay + host", row["check_in"] == "10:00" and row["check_out"] == "11:30"
          and row["minutes"] == 90 and row["host"] == "Dev T", row)
    check("chart per day (line)", d["chart"]["type"] == "line" and sum(d["chart"]["series"][0]["data"]) == 3, d["chart"])
    s, b = post(C["hr"], "reports/visitors/", {"still_inside": True})
    check("still_inside filter", s == 200 and [r["visit_code"] for r in b["data"]["rows"]] == ["B18V3"], b)
    s, b = post(C["hr"], "reports/visitors/", {"purpose": "CLIENT", "search": "acme"})
    check("purpose + search", s == 200 and [r["visit_code"] for r in b["data"]["rows"]] == ["B18V1"], b)
    s, b = post(C["hr"], "reports/visitors/", {"view": "summary"})
    rows = {r["group"]: r for r in b["data"]["rows"]}
    check("summary by host (incl. No host)", s == 200 and rows["Dev T"]["visits"] == 1 and rows["Dev T"]["visitors"] == 2
          and "No host" in rows and b["data"]["totals"]["visits"] == 3, b)
    s, b = post(C["hr"], "reports/visitors/", {"view": "summary", "group_by": "purpose"})
    check("summary by purpose", s == 200 and {r["group"] for r in b["data"]["rows"]}
          == {"Client visit", "Interview", "Delivery"}, b)
    s, b = post(C["hr"], "reports/visitors/", {"view": "summary", "group_by": "day"})
    check("summary by day covers every day", s == 200 and len(b["data"]["rows"])
          == (b["data"]["filters"] and (date.fromisoformat(b["data"]["filters"]["to_date"])
                                         - date.fromisoformat(b["data"]["filters"]["from_date"])).days + 1), b)
    s, b = post(C["hr"], "reports/visitors/", {"view": "summary", "group_by": "branch"})
    check("bad group_by -> 400", s == 400, b)
    s, b = post(C["owner"], "reports/visitors/", {"format": "xlsx"})
    check("visitors xlsx download", s == 200 and b.get("xlsx"), b)


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
print(f"\nBatch 18: {passed}/{len(RESULTS)} passed (all changes rolled back)")
if passed != len(RESULTS):
    sys.exit(1)
