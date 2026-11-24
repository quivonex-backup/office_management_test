"""
Batch 15 checks: leave carry forward (LeaveType.carry_forward_enabled /
max_carry_forward_days, leave/balances/carry-forward/).

Run after makemigrations + migrate; any database; everything is rolled back:
    python manage.py shell -c "exec(open('scripts/test_batch15.py').read())"
"""
import sys
import traceback
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from app.accounts.models import AccessRole, Organization, OrganizationMembership, Role, User
from app.accounts.services import seed_organization_defaults
from app.employees.models import Employee
from app.leave.models import EmployeeLeaveBalance, LeaveBalanceTransaction, LeaveType

RESULTS = []
D = Decimal
THIS_YEAR = timezone.localdate().year
OLD = THIS_YEAR - 1          # a finished year
NEW = THIS_YEAR


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


def run():
    admin_role, _ = Role.objects.get_or_create(name="Admin", defaults={"is_active": True})
    emp_role, _ = Role.objects.get_or_create(name="Employee", defaults={"is_active": True})
    n = [0]

    def user(name, role=emp_role):
        n[0] += 1
        return User.objects.create(username=f"b15_{name}", email=f"b15_{name}@x.test", mobile=f"15000000{n[0]:02d}",
                                   role=role, first_name=name.title())

    owner = user("owner", admin_role)
    org = Organization.objects.create(organization_name="B15 Org", owner=owner)
    OrganizationMembership.objects.create(organization=org, user=owner, is_active=True)
    seed_organization_defaults(org)

    def employee(name, **kw):
        u = user(name)
        OrganizationMembership.objects.create(organization=org, user=u, is_active=True)
        return Employee.objects.create(organization=org, first_name=name.title(), last_name="T",
                                       employee_code=f"B15-{name}", user=u, employment_status="ACTIVE", **kw)

    a, b_, c, gone = employee("a"), employee("b"), employee("c"), employee("gone")
    Employee.objects.filter(pk=gone.pk).update(is_active=False, employment_status="RESIGNED")
    C = {"owner": client_for(owner), "a": client_for(a.user)}

    # ================= LEAVE TYPE FIELDS
    s, b = post(C["owner"], "leave/types/create/", {"name": "Earned Leave", "code": "EL", "annual_allocation": "15",
                                                  "carry_forward_enabled": True, "max_carry_forward_days": "10"})
    check("type create with carry forward fields", s == 201 and b["data"]["carry_forward_enabled"] is True
          and b["data"]["max_carry_forward_days"] == "10.00", b)
    el = LeaveType.objects.get(pk=b["data"]["id"])
    s, b = post(C["owner"], "leave/types/create/", {"name": "Casual", "code": "CL", "annual_allocation": "8"})
    check("default: carry forward off, no limit", s == 201 and b["data"]["carry_forward_enabled"] is False
          and b["data"]["max_carry_forward_days"] is None, b)
    cl = LeaveType.objects.get(pk=b["data"]["id"])
    s, b = post(C["owner"], "leave/types/create/", {"name": "Comp", "code": "CO", "annual_allocation": "5",
                                                  "carry_forward_enabled": True})
    co = LeaveType.objects.get(pk=b["data"]["id"])        # no limit
    s, b = post(C["owner"], "leave/types/update/", {"leave_type_id": cl.id, "max_carry_forward_days": "-1"})
    check("negative max -> 400", s == 400, b)

    # ================= OLD-YEAR BALANCES
    def bal(emp, lt, year, opening="0", alloc="0", used="0", pending="0"):
        return EmployeeLeaveBalance.objects.create(organization=org, employee=emp, leave_type=lt, leave_year=year,
                                                   opening_balance=D(opening), allocated_days=D(alloc),
                                                   used_days=D(used), pending_days=D(pending))

    bal(a, el, OLD, alloc="15", used="2")                 # 13 unused -> 10 (cap), 3 lapse
    bal(b_, el, OLD, opening="2", alloc="15", used="10", pending="1")   # 6 unused -> 6
    bal(c, el, OLD, alloc="15", used="15")                # 0 -> nothing
    bal(a, cl, OLD, alloc="8")                            # CL off -> ignored
    bal(a, co, OLD, alloc="5", used="1")                  # 4 -> 4 (no limit)
    bal(gone, el, OLD, alloc="15")                        # resigned -> ignored
    pre_new_b = bal(b_, el, NEW, alloc="15", used="1")    # already initialized for new year

    s, b = post(C["a"], "leave/balances/carry-forward/", {"from_year": OLD})
    check("employee -> 403", s == 403, s)
    s, b = post(C["owner"], "leave/balances/carry-forward/", {})
    check("from_year required -> 400", s == 400, b)
    s, b = post(C["owner"], "leave/balances/carry-forward/", {"from_year": THIS_YEAR})
    check("current year not finished -> 400 (suggests dry_run)", s == 400 and "dry_run" in b["message"], b)
    s, b = post(C["owner"], "leave/balances/carry-forward/", {"from_year": THIS_YEAR, "dry_run": True})
    check("current year preview allowed", s == 200 and b["data"]["dry_run"] is True, b)
    s, b = post(C["owner"], "leave/balances/carry-forward/", {"from_year": OLD, "leave_type_ids": [cl.id]})
    check("type with carry forward off in leave_type_ids -> 400", s == 400, b)

    # ---- preview
    s, b = post(C["owner"], "leave/balances/carry-forward/", {"from_year": OLD, "dry_run": True})
    d = b.get("data") or {}
    rows = {(r["employee_code"], r["leave_type"]): r for r in d.get("rows", [])}
    check("preview: rows only for enabled types + active employees",
          s == 200 and set(rows) == {("B15-a", "Earned Leave"), ("B15-b", "Earned Leave"), ("B15-c", "Earned Leave"),
                                     ("B15-a", "Comp")}, list(rows))
    check("preview amounts: cap 10 (3 lapse), pending excluded, zero, no limit",
          rows[("B15-a", "Earned Leave")]["carry_forward_days"] == "10.00"
          and rows[("B15-a", "Earned Leave")]["lapsed_days"] == "3.00"
          and rows[("B15-b", "Earned Leave")]["carry_forward_days"] == "6.00"
          and rows[("B15-c", "Earned Leave")]["result"] == "NOTHING_TO_CARRY"
          and rows[("B15-a", "Comp")]["carry_forward_days"] == "4.00", rows)
    check("preview summary", d["summary"]["carried"] == 3 and d["summary"]["total_days_carried"] == "20.00"
          and d["summary"]["total_days_lapsed"] == "3.00", d.get("summary"))
    check("preview saved nothing", not EmployeeLeaveBalance.objects.filter(employee=a, leave_year=NEW).exists()
          and not LeaveBalanceTransaction.objects.filter(organization=org, transaction_type="CARRY_FORWARD").exists())

    # ---- run
    s, b = post(C["owner"], "leave/balances/carry-forward/", {"from_year": OLD})
    check("run -> 200", s == 200 and b["data"]["summary"]["carried"] == 3 and b["data"]["dry_run"] is False, b)
    na = EmployeeLeaveBalance.objects.get(employee=a, leave_type=el, leave_year=NEW)
    check("new balance created with allocation + opening 10", na.opening_balance == D("10")
          and na.allocated_days == D("15") and na.available == D("25"), (na.opening_balance, na.allocated_days))
    check("ALLOCATION + CARRY_FORWARD transactions",
          set(na.transactions.values_list("transaction_type", flat=True)) == {"ALLOCATION", "CARRY_FORWARD"}
          and na.transactions.get(transaction_type="CARRY_FORWARD").days == D("10"))
    pre_new_b.refresh_from_db()
    check("existing new-year balance: opening added, allocation untouched",
          pre_new_b.opening_balance == D("6") and pre_new_b.allocated_days == D("15") and pre_new_b.used_days == D("1"))
    old_a = EmployeeLeaveBalance.objects.get(employee=a, leave_type=el, leave_year=OLD)
    check("old year balance unchanged", old_a.used_days == D("2") and old_a.allocated_days == D("15"))
    check("nothing for CL (off) or resigned employee",
          not EmployeeLeaveBalance.objects.filter(leave_type=cl, leave_year=NEW).exists()
          and not EmployeeLeaveBalance.objects.filter(employee=gone, leave_year=NEW).exists())

    # ---- run again: idempotent
    s, b = post(C["owner"], "leave/balances/carry-forward/", {"from_year": OLD})
    na.refresh_from_db()
    check("second run skips (ALREADY_DONE), no double opening",
          s == 200 and b["data"]["summary"]["skipped_already_done"] == 3 and na.opening_balance == D("10"), b)

    # ---- old year changed (late cancellation gives back 2 days to b) -> recalculate
    EmployeeLeaveBalance.objects.filter(employee=b_, leave_type=el, leave_year=OLD).update(used_days=D("8"))
    s, b = post(C["owner"], "leave/balances/carry-forward/", {"from_year": OLD, "recalculate": True, "dry_run": True})
    r = next(x for x in b["data"]["rows"] if x["employee_code"] == "B15-b")
    check("recalculate preview: +2", r["result"] == "UPDATED" and r["change_days"] == "2.00", r)
    s, b = post(C["owner"], "leave/balances/carry-forward/", {"from_year": OLD, "recalculate": True})
    pre_new_b.refresh_from_db()
    check("recalculate: opening 6 -> 8, delta logged",
          pre_new_b.opening_balance == D("8") and list(pre_new_b.transactions.filter(
              transaction_type="CARRY_FORWARD").order_by("id").values_list("days", flat=True)) == [D("6"), D("2")], b)

    # lowering below what is already used -> per-row error
    EmployeeLeaveBalance.objects.filter(employee=b_, leave_type=el, leave_year=NEW).update(used_days=D("23"))
    EmployeeLeaveBalance.objects.filter(employee=b_, leave_type=el, leave_year=OLD).update(used_days=D("17"))
    s, b = post(C["owner"], "leave/balances/carry-forward/", {"from_year": OLD, "recalculate": True})
    r = next(x for x in b["data"]["rows"] if x["employee_code"] == "B15-b")
    pre_new_b.refresh_from_db()
    check("recalculate that would go negative -> row ERROR, balance kept",
          r["result"] == "ERROR" and b["data"]["summary"]["errors"] == 1 and pre_new_b.opening_balance == D("8"), r)

    # ---- employee sees opening balance
    s, b = post(C["a"], "leave/balances/my/", {"leave_year": NEW})
    el_row = next((x for x in b.get("data", []) if x["leave_type"] == el.id), None)
    check("employee balances show opening_balance + available",
          s == 200 and el_row and el_row["opening_balance"] == "10.00" and D(str(el_row["available_days"])) == D("25"),
          b)

    s, b = post(C["owner"], "leave/transactions/list/", {"transaction_type": "CARRY_FORWARD"})
    check("transactions list includes CARRY_FORWARD", s == 200 and "CARRY_FORWARD" in str(b), str(b)[:300])

    LeaveType.objects.filter(organization=org).update(carry_forward_enabled=False)
    s, b = post(C["owner"], "leave/balances/carry-forward/", {"from_year": OLD})
    check("no type enabled -> 400", s == 400, b)


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
print(f"\nBatch 15: {passed}/{len(RESULTS)} passed (all changes rolled back)")
if passed != len(RESULTS):
    sys.exit(1)
