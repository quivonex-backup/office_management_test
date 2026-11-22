"""
Batch 1 checks: branches, departments, designations, access roles,
permissions, my-profile, employee assignments, org-create seeding,
assign-owner downgrade.

Run after `makemigrations accounts employees` + `migrate`
(any database; everything is rolled back at the end):
    python manage.py shell -c "exec(open('scripts/test_batch1.py').read())"

External calls are stubbed: S3 upload, email (locmem backend).
Prints one line per check and a summary; exits the shell with code 1 on failure.
"""
import sys
import traceback
from unittest import mock

from django.db import transaction
from django.test.utils import override_settings
from rest_framework.test import APIClient

from app.accounts.models import AccessRole, Branch, Organization, OrganizationMembership, Permission, Role, User
from app.accounts.permission_catalog import ALL_CODES, DEFAULT_ACCESS_ROLES, SELF_SERVICE_CODES
from app.accounts.services import seed_organization_defaults
from app.employees.models import Department, Designation, Employee
from common.services import get_team_employee_ids

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


def make_user(username, email, mobile, role, superuser=False):
    u = User.objects.create(username=username, email=email, mobile=mobile, role=role,
                            is_superuser=superuser, is_staff=superuser)
    u.set_password("x-test-123")
    u.save()
    return u


def make_employee(org, first, user=None, **kw):
    e = Employee.objects.create(organization=org, first_name=first, last_name="T",
                                employee_code=f"T-{first}", user=user, **kw)
    if user:
        OrganizationMembership.objects.get_or_create(organization=org, user=user, defaults={"is_active": True})
    return e


def run():
    admin_role, _ = Role.objects.get_or_create(name="Admin", defaults={"is_active": True})
    emp_role, _ = Role.objects.get_or_create(name="Employee", defaults={"is_active": True})

    owner = make_user("t_owner", "t_owner@x.test", "9000000001", admin_role)
    org = Organization.objects.create(organization_name="T Org A", owner=owner)
    OrganizationMembership.objects.create(organization=org, user=owner, is_active=True)
    org_b = Organization.objects.create(organization_name="T Org B")
    seed_organization_defaults(org)
    seed_organization_defaults(org_b)

    roles = {r.name: r for r in AccessRole.objects.filter(organization=org)}
    check("seed: 4 default access roles", set(roles) == set(DEFAULT_ACCESS_ROLES), list(roles))
    check("seed: permission catalog synced", Permission.objects.count() >= len(ALL_CODES))
    seed_organization_defaults(org)
    check("seed: idempotent", AccessRole.objects.filter(organization=org).count() == 4)

    hr_user = make_user("t_hr", "t_hr@x.test", "9000000002", emp_role)
    mgr_user = make_user("t_mgr", "t_mgr@x.test", "9000000003", emp_role)
    emp_user = make_user("t_emp", "t_emp@x.test", "9000000004", emp_role)
    su = make_user("t_su", "t_su@x.test", "9000000005", None, superuser=True)

    hr = make_employee(org, "Hr", hr_user, access_role=roles["HR Manager"])
    mgr = make_employee(org, "Mgr", mgr_user, access_role=roles["Department Manager"])
    emp = make_employee(org, "Emp", emp_user)

    C_owner, C_hr, C_mgr, C_emp, C_su = (client_for(u) for u in (owner, hr_user, mgr_user, emp_user, su))

    # ---------------- my-profile
    s, b = post(C_owner, "accounts/my-profile/")
    check("my-profile owner: 200 + all permissions",
          s == 200 and b["data"]["permissions"] == sorted(ALL_CODES) and b["data"]["is_org_owner"], b)
    check("my-profile keeps old fields", "role_details" in b["data"] and "username" in b["data"], list(b.get("data", {})))
    s, b = post(C_hr, "accounts/my-profile/")
    expected = sorted(set(DEFAULT_ACCESS_ROLES["HR Manager"]["codes"]) | set(SELF_SERVICE_CODES))
    check("my-profile HR: access role + codes",
          s == 200 and b["data"]["access_role"]["name"] == "HR Manager" and b["data"]["permissions"] == expected, b)
    s, b = post(C_emp, "accounts/my-profile/")
    check("my-profile plain employee: self-service only + employee block",
          s == 200 and b["data"]["permissions"] == sorted(SELF_SERVICE_CODES)
          and b["data"]["employee"]["id"] == emp.id and b["data"]["access_role"] is None, b)
    s, b = post(C_su, "accounts/my-profile/")
    check("my-profile super admin without org: 200, nulls",
          s == 200 and b["data"]["organization"] is None and b["data"]["permissions"] == [], b)

    # ---------------- branches
    s, b = post(C_emp, "accounts/branch/create/", {"name": "Pune"})
    check("branch create by plain employee: 403", s == 403, (s, b))
    s, b = post(C_owner, "accounts/branch/create/",
                {"name": "Pune HQ", "city": "Pune", "latitude": "18.520400", "longitude": "73.856700",
                 "allowed_radius_meters": 150})
    check("branch create by owner: 201", s == 201 and b["data"]["name"] == "Pune HQ", (s, b))
    pune_id = b["data"]["id"]
    s, b = post(C_owner, "accounts/branch/create/", {"name": "pune hq"})
    check("branch duplicate name (case-insensitive): 400", s == 400 and "name" in b.get("errors", {}), (s, b))
    s, b = post(C_owner, "accounts/branch/create/", {"name": "Mumbai", "latitude": "19.07"})
    check("branch latitude without longitude: 400", s == 400, (s, b))
    s, b = post(C_owner, "accounts/branch/create/", {"name": "Mumbai"})
    mumbai_id = b["data"]["id"]
    s, b = post(C_owner, "accounts/branch/update/", {"branch_id": mumbai_id, "city": "Mumbai"})
    check("branch update: 200", s == 200 and b["data"]["city"] == "Mumbai", (s, b))
    other_branch = Branch.objects.create(organization=org_b, name="B Only")
    s, b = post(C_owner, "accounts/branch/update/", {"branch_id": other_branch.id, "city": "X"})
    check("branch of another org: 404", s == 404, (s, b))

    # ---------------- departments / designations
    s, b = post(C_hr, "employees/department/create/", {"name": "Engineering"})
    check("department create without org.manage: 403", s == 403, (s, b))
    s, b = post(C_owner, "employees/department/create/", {"name": "Engineering", "code": "ENG"})
    check("department create by owner: 201", s == 201, (s, b))
    eng_id = b["data"]["id"]
    s, b = post(C_owner, "employees/designation/create/", {"name": "Software Engineer"})
    check("designation create by owner: 201", s == 201, (s, b))
    se_id = b["data"]["id"]
    s, b = post(C_emp, "employees/department/list/")
    check("department list by any member: 200", s == 200 and len(b["data"]) == 1, (s, b))

    # ---------------- permissions / access roles
    s, b = post(C_hr, "accounts/access-role/list/")
    check("access-role list without access.manage: 403", s == 403, (s, b))
    s, b = post(C_owner, "accounts/access-role/list/")
    check("access-role list owner: 4 roles with codes",
          s == 200 and len(b["data"]) == 4 and all(r["permission_codes"] for r in b["data"]), (s, b))
    s, b = post(C_owner, "accounts/permission/list/")
    check("permission list: full catalog", s == 200 and len(b["data"]) == len(ALL_CODES), (s, len(b.get("data", []))))
    s, b = post(C_owner, "accounts/access-role/create/", {"name": "Team Lead", "permission_codes": ["nope.code"]})
    check("access-role create with unknown code: 400", s == 400, (s, b))
    s, b = post(C_owner, "accounts/access-role/create/",
                {"name": "Team Lead", "permission_codes": ["leave.view_team", "leave.approve", "leave.approve"]})
    check("access-role create: 201, codes de-duplicated",
          s == 201 and b["data"]["permission_codes"] == ["leave.approve", "leave.view_team"], (s, b))
    tl_id = b["data"]["id"]
    s, b = post(C_owner, "accounts/access-role/update/", {"access_role_id": tl_id, "permission_codes": ["employee.view_team"]})
    check("access-role update replaces codes", s == 200 and b["data"]["permission_codes"] == ["employee.view_team"], (s, b))
    s, b = post(C_owner, "accounts/access-role/update/", {"access_role_id": tl_id, "description": "Leads"})
    check("access-role update without codes keeps codes",
          s == 200 and b["data"]["permission_codes"] == ["employee.view_team"], (s, b))
    s, b = post(C_owner, "accounts/access-role/deactivate/", {"access_role_id": roles["HR Manager"].id})
    check("access-role deactivate while assigned: 400", s == 400, (s, b))

    # ---------------- employee create / update
    with mock.patch("app.employees.views.upload_to_s3", return_value="stub/path"):
        s, b = post(C_emp, "employees/create/", {"first_name": "No", "last_name": "Perm"})
        check("employee create by plain employee: 403", s == 403, (s, b))

        s, b = post(C_owner, "employees/create/", {"first_name": "Old", "last_name": "Client", "department": "Free text"})
        check("employee create with old payload still works", s == 201 and b["data"]["department"] == "Free text"
              and b["data"]["department_ref"] is None, (s, b))

        s, b = post(C_hr, "employees/create/", {
            "first_name": "New", "last_name": "Hire", "branch_id": pune_id,
            "department_id": eng_id, "designation_id": se_id, "reports_to_id": mgr.id})
        d = b.get("data", {})
        check("employee create by HR with masters: 201 + text synced",
              s == 201 and d["branch"]["id"] == pune_id and d["department"] == "Engineering"
              and d["designation"] == "Software Engineer" and d["reports_to"]["id"] == mgr.id, (s, b))
        new_id = d.get("id")

        s, b = post(C_hr, "employees/create/", {"first_name": "X", "last_name": "Y",
                                                "access_role_id": roles["HR Executive"].id})
        check("HR cannot assign access role (no access.manage): 400", s == 400 and "access_role_id" in b.get("errors", {}), (s, b))

        s, b = post(C_owner, "employees/create/", {"first_name": "X", "last_name": "Y", "branch_id": other_branch.id})
        check("branch from another organization: 400", s == 400 and "branch_id" in b.get("errors", {}), (s, b))

        s, b = post(C_owner, "employees/update/", {"employee_id": emp.id, "access_role_id": roles["HR Executive"].id},
                    multipart=True)
        check("owner assigns access role via employees/update", s == 200 and b["data"]["access_role"]["name"] == "HR Executive", (s, b))
        s, b = post(C_emp, "accounts/my-profile/")
        check("assigned role reflected in my-profile", "applicant.create" in b["data"]["permissions"], b["data"]["permissions"])

        # reporting loops: emp -> mgr, then mgr -> emp must fail; self must fail
        post(C_owner, "employees/update/", {"employee_id": emp.id, "reports_to_id": mgr.id}, multipart=True)
        s, b = post(C_owner, "employees/update/", {"employee_id": mgr.id, "reports_to_id": emp.id}, multipart=True)
        check("reporting loop rejected", s == 400 and "reports_to_id" in b.get("errors", {}), (s, b))
        s, b = post(C_owner, "employees/update/", {"employee_id": mgr.id, "reports_to_id": mgr.id}, multipart=True)
        check("self as manager rejected", s == 400, (s, b))

        s, b = post(C_owner, "employees/update/", {"employee_id": emp.id, "department": "engineering"}, multipart=True)
        check("legacy text matching a master links department_ref",
              s == 200 and b["data"]["department_ref"] and b["data"]["department_ref"]["id"] == eng_id, (s, b))

        s, b = post(C_owner, "employees/update/", {"employee_id": emp.id, "department_id": ""}, multipart=True)
        check("blank department_id clears link and text",
              s == 200 and b["data"]["department_ref"] is None and b["data"]["department"] is None, (s, b))

    # ---------------- team helper
    team = get_team_employee_ids(mgr)
    check("team = manager + direct + indirect reports", set(team) == {mgr.id, emp.id, new_id}, team)

    # ---------------- list filters / masters protection
    s, b = post(C_owner, "employees/list/", {"department_id": eng_id})
    check("employees/list department filter", s == 200 and [r["id"] for r in b["data"]] == [new_id], (s, b))
    s, b = post(C_owner, "employees/list/", {"branch_id": "abc"})
    check("employees/list bad filter: 400", s == 400, (s, b))
    s, b = post(C_owner, "employees/department/deactivate/", {"department_id": eng_id})
    check("department deactivate while in use: 400", s == 400, (s, b))
    s, b = post(C_owner, "employees/department/update/", {"department_id": eng_id, "name": "Engineering & QA"})
    check("department rename: 200", s == 200, (s, b))
    check("rename syncs employee text", Employee.objects.get(pk=new_id).department == "Engineering & QA")
    s, b = post(C_owner, "accounts/branch/list/")
    pune = next(x for x in b["data"] if x["id"] == pune_id)
    check("branch list employee_count", pune["employee_count"] == 1, pune)

    # ---------------- organization create seeds roles (super admin)
    with mock.patch("app.accounts.views.upload_to_s3", return_value=None):
        s, b = post(C_su, "accounts/organization/create/", {"organization_name": "T Org Created"})
    ok = s == 201 and AccessRole.objects.filter(organization_id=b["data"]["id"]).count() == 4
    check("organization/create seeds 4 access roles", ok, (s, b))

    # ---------------- assign-owner downgrades previous owner to Employee
    new_owner = make_user("t_owner2", "t_owner2@x.test", "9000000006", emp_role)
    OrganizationMembership.objects.create(organization=org, user=new_owner, is_active=True)
    s, b = post(C_su, "accounts/organization/assign-owner/", {"organization_id": org.id, "user_id": new_owner.id})
    owner.refresh_from_db()
    check("assign-owner: 200 and old owner becomes Employee",
          s == 200 and owner.role_id == emp_role.id, (s, b, owner.role))
    s, b = post(C_owner, "accounts/branch/create/", {"name": "After Downgrade"})
    check("old owner lost admin rights", s == 403, (s, b))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   ALLOWED_HOSTS=["*"])
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
