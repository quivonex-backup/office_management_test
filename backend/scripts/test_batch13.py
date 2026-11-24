"""
Batch 13 checks: payroll salary components detail / update / deactivate.

Run after migrate; any database; everything is rolled back:
    python manage.py shell -c "exec(open('scripts/test_batch13.py').read())"
"""
import sys
import traceback
from decimal import Decimal

from django.db import transaction
from rest_framework.test import APIClient

from app.accounts.models import AccessRole, Organization, OrganizationMembership, Role, User
from app.accounts.services import seed_organization_defaults
from app.employees.models import Employee
from app.payroll.models import SalaryComponent, SalaryStructure, SalaryStructureComponent

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
        return User.objects.create(username=f"b13_{name}", email=f"b13_{name}@x.test", mobile=f"13000000{n[0]:02d}",
                                   role=role, first_name=name.title())

    owner = user("owner", admin_role)
    org = Organization.objects.create(organization_name="B13 Org", owner=owner)
    OrganizationMembership.objects.create(organization=org, user=owner, is_active=True)
    seed_organization_defaults(org)
    roles = {r.name: r for r in AccessRole.objects.filter(organization=org)}
    other_owner = user("other", admin_role)
    other = Organization.objects.create(organization_name="B13 Other", owner=other_owner)

    def employee(name, role=None):
        u = user(name)
        OrganizationMembership.objects.create(organization=org, user=u, is_active=True)
        return Employee.objects.create(organization=org, first_name=name.title(), last_name="T",
                                       employee_code=f"B13-{name}", user=u, access_role=role,
                                       employment_status="ACTIVE")

    pay = employee("pay", roles["Payroll Manager"])
    plain = employee("plain")
    C = {"owner": client_for(owner), "pay": client_for(pay.user), "plain": client_for(plain.user)}

    def comp(code, ctype="EARNING", o=org, **kw):
        return SalaryComponent.objects.create(organization=o, name=code.title(), code=code, component_type=ctype, **kw)

    glob = SalaryComponent.objects.create(organization=None, name="Global Basic B13", code="B13GB",
                                          component_type="EARNING")
    basic = comp("B13BASIC", component_role="BASIC")
    hra = comp("B13HRA", calculation_type="PERCENTAGE", percentage_of_component=basic, component_role="HRA")
    bonus = comp("B13BONUS")
    spare = comp("B13SPARE")
    foreign = comp("B13FOR", o=other)

    st = SalaryStructure.objects.create(organization=org, name="Engineer", code="B13ENG")
    SalaryStructureComponent.objects.create(salary_structure=st, salary_component=basic, amount=D("30000"))
    SalaryStructureComponent.objects.create(salary_structure=st, salary_component=hra, percentage=D("40"))
    old_st = SalaryStructure.objects.create(organization=org, name="Old", code="B13OLD", is_active=False)
    SalaryStructureComponent.objects.create(salary_structure=old_st, salary_component=bonus, amount=D("1000"))

    # ================= PERMISSION / SCOPE
    s, _ = post(C["plain"], "payroll/components/detail/", {"component_id": basic.id})
    check("plain employee -> 403", s == 403, s)
    s, b = post(C["pay"], "payroll/components/detail/", {"component_id": basic.id})
    d = b.get("data") or {}
    check("detail: usage + locked", s == 200 and [x["name"] for x in d["used_in_structures"]] == ["Engineer"]
          and d["is_locked"] and "code" in d["locked_fields"]
          and [x["code"] for x in d["percentage_dependents"]] == ["B13HRA"] and d["is_global"] is False, b)
    s, b = post(C["pay"], "payroll/components/detail/", {"component_id": glob.id})
    check("detail of a global component works (read-only)", s == 200 and b["data"]["is_global"], b)
    s, b = post(C["pay"], "payroll/components/detail/", {"component_id": foreign.id})
    check("other org's component -> 404", s == 404, b)
    s, b = post(C["pay"], "payroll/components/detail/", {})
    check("component_id required -> 400", s == 400, b)

    # ================= UPDATE
    s, b = post(C["pay"], "payroll/components/update/", {"component_id": glob.id, "name": "X"})
    check("global component update -> 403", s == 403, b)
    s, b = post(C["pay"], "payroll/components/update/", {"component_id": basic.id, "name": "Basic Pay",
                                                       "display_order": 1, "is_pf_eligible": True})
    basic.refresh_from_db()
    check("used component: name / order / flags editable", s == 200 and basic.name == "Basic Pay"
          and basic.display_order == 1 and basic.is_pf_eligible, b)
    s, b = post(C["pay"], "payroll/components/update/", {"component_id": basic.id, "code": "NEWCODE",
                                                       "component_type": "DEDUCTION"})
    check("used component: code / type locked -> 400", s == 400 and set(b.get("errors", {})) == {"code", "component_type"}, b)
    s, b = post(C["pay"], "payroll/components/update/", {"component_id": basic.id, "code": "b13basic",
                                                       "component_type": "EARNING", "name": "Basic"})
    check("used component: sending unchanged locked values is fine", s == 200 and b["data"]["name"] == "Basic", b)
    s, b = post(C["pay"], "payroll/components/update/", {"component_id": hra.id, "percentage_of_component": bonus.id})
    check("used component: percentage parent locked", s == 400 and "percentage_of_component" in b.get("errors", {}), b)
    s, b = post(C["pay"], "payroll/components/update/", {"component_id": bonus.id, "code": "B13BON2"})
    check("used in an INACTIVE structure still locks code", s == 400, b)

    s, b = post(C["pay"], "payroll/components/update/", {"component_id": spare.id, "code": "b13extra",
                                                       "component_type": "DEDUCTION", "component_role": "OTHER"})
    spare.refresh_from_db()
    check("unused component: code / type editable (code upper-cased)", s == 200 and spare.code == "B13EXTRA"
          and spare.component_type == "DEDUCTION" and b["data"]["is_locked"] is False, b)
    s, b = post(C["pay"], "payroll/components/update/", {"component_id": spare.id, "code": "B13HRA"})
    check("duplicate code -> 400", s == 400 and "code" in b.get("errors", {}), b)
    s, b = post(C["pay"], "payroll/components/update/", {"component_id": spare.id, "calculation_type": "PERCENTAGE"})
    check("PERCENTAGE without parent -> 400", s == 400 and "percentage_of_component" in b.get("errors", {}), b)
    s, b = post(C["pay"], "payroll/components/update/", {"component_id": spare.id, "calculation_type": "PERCENTAGE",
                                                       "percentage_of_component": foreign.id})
    check("parent from other org -> 400", s == 400 and "percentage_of_component" in b.get("errors", {}), b)
    s, b = post(C["pay"], "payroll/components/update/", {"component_id": spare.id, "calculation_type": "PERCENTAGE",
                                                       "percentage_of_component": spare.id})
    check("self as parent -> 400", s == 400, b)
    s, b = post(C["pay"], "payroll/components/update/", {"component_id": spare.id, "calculation_type": "PERCENTAGE",
                                                       "percentage_of_component": basic.id})
    spare.refresh_from_db()
    check("unused: switch to PERCENTAGE of basic", s == 200 and spare.percentage_of_component_id == basic.id, b)
    s, b = post(C["pay"], "payroll/components/update/", {"component_id": spare.id})
    check("nothing to update -> 400", s == 400, b)
    s, b = post(C["pay"], "payroll/components/update/", {"component_id": spare.id, "is_active": False})
    check("is_active false via update -> 400 (use deactivate)", s == 400, b)

    # ================= DEACTIVATE
    s, b = post(C["pay"], "payroll/components/deactivate/", {"component_id": glob.id})
    check("global component deactivate -> 403", s == 403, b)
    s, b = post(C["pay"], "payroll/components/deactivate/", {"component_id": hra.id})
    check("used in active structure -> 400 with names", s == 400 and "Engineer" in b["message"]
          and b["errors"]["used_in_structures"][0]["code"] == "B13ENG", b)
    st.components.filter(salary_component=hra).delete()
    s, b = post(C["pay"], "payroll/components/deactivate/", {"component_id": hra.id})
    check("removed from structure -> deactivated", s == 200, b)
    s, b = post(C["pay"], "payroll/components/deactivate/", {"component_id": hra.id})
    check("already inactive -> 400", s == 400, b)
    s, b = post(C["pay"], "payroll/components/deactivate/", {"component_id": bonus.id})
    check("used only in inactive structure -> deactivated", s == 200, b)

    st.is_active = False
    st.save()
    s, b = post(C["pay"], "payroll/components/deactivate/", {"component_id": basic.id})
    check("active percentage dependent blocks deactivate", s == 400 and "B13EXTRA" in str(b.get("errors")), b)
    SalaryComponent.objects.filter(pk=spare.pk).update(is_active=False)
    s, b = post(C["pay"], "payroll/components/deactivate/", {"component_id": basic.id})
    check("no active users -> basic deactivated", s == 200, b)

    s, b = post(C["pay"], "payroll/components/list/", {"is_active": False})
    check("list shows inactive ones", s == 200 and {"B13HRA", "B13BONUS", "B13BASIC"} <= {c["code"] for c in b["data"]}, b)
    s, b = post(C["pay"], "payroll/structures/create/", {"name": "New", "code": "B13NEW", "components": [
        {"salary_component": bonus.id, "amount": "100"}]})
    check("inactive component refused in new structure", s == 400, b)

    # ================= REACTIVATE
    s, b = post(C["pay"], "payroll/components/update/", {"component_id": spare.id, "is_active": True})
    check("reactivate refused while parent inactive", s == 400 and "Basic" in b["message"], b)
    s, b = post(C["owner"], "payroll/components/update/", {"component_id": basic.id, "is_active": True})
    check("owner reactivates basic", s == 200 and b["data"]["is_active"], b)
    s, b = post(C["pay"], "payroll/components/update/", {"component_id": spare.id, "is_active": True})
    check("then dependent reactivates", s == 200 and b["data"]["is_active"], b)
    s, b = post(client_for(other_owner), "payroll/components/update/", {"component_id": basic.id, "name": "Hack"})
    check("other org owner -> 404", s == 404, b)


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
print(f"\nBatch 13: {passed}/{len(RESULTS)} passed (all changes rolled back)")
if passed != len(RESULTS):
    sys.exit(1)
