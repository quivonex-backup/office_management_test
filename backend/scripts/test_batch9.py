"""
Batch 9 checks: payment reminder status codes (400 data / 502 mail),
payroll "ABSENT" missing-attendance as a note (no review block), and no
project / task / project-chat access for the platform super admin.

Run after migrate; any database; everything is rolled back:
    python manage.py shell -c "exec(open('scripts/test_batch9.py').read())"
"""
import sys
import traceback
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.db import transaction
from rest_framework.test import APIClient

from app.accounts.models import Organization, OrganizationMembership, Role, User
from app.accounts.services import seed_organization_defaults
from app.clients.models import Client
from app.payments.models import ProjectPayment
from app.payroll.services.attendance import classify_period
from app.projects.models import Project
from common.services import get_accessible_projects, get_project_permission

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print(("PASS " if condition else "FAIL ") + name + ("" if condition else f"  -> {detail}"))


class Rollback(Exception):
    pass


def post(c, url, data=None):
    r = c.post("/" + url, data or {}, format="json")
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.content[:200]}


def run():
    admin_role, _ = Role.objects.get_or_create(name="Admin", defaults={"is_active": True})
    owner = User.objects.create(username="b9_owner", email="b9_owner@x.test", mobile="9000000101", role=admin_role)
    org = Organization.objects.create(organization_name="B9 Org", owner=owner, email="acc@b9.test")
    OrganizationMembership.objects.create(organization=org, user=owner, is_active=True)
    seed_organization_defaults(org)
    C = APIClient()
    C.force_authenticate(user=owner)

    client = Client.objects.create(organization=org, client_code="B9-CL1", client_name="ABC Technologies",
                                   email="contact@abc.test")
    project = Project.objects.create(organization=org, client=client, project_code="B9-PR1", project_name="Portal",
                                     total_cost=Decimal("100000"))

    # ================= 1. payment reminder
    s, b = post(C, "payments/payment-reminder/", {"project_ids": [project.id]})
    fc = (b.get("data") or {}).get("failed_clients") or [{}]
    check("no payment rows -> 400 (not 500) with failure_type DATA",
          s == 400 and fc[0].get("failure_type") == "DATA" and "No active payment plans" in fc[0].get("reason", ""),
          (s, b))

    fields = {f.name for f in ProjectPayment._meta.get_fields()}
    extra = {"organization": org} if "organization" in fields else {}
    ProjectPayment.objects.create(project=project, payment_type="ADVANCE", amount=Decimal("20000"),
                                  due_date=date(2026, 12, 1), **extra)
    with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("SMTP down")):
        s, b = post(C, "payments/payment-reminder/", {"project_ids": [project.id]})
    fc = (b.get("data") or {}).get("failed_clients") or [{}]
    check("mail server failure -> 502 with failure_type SEND_ERROR",
          s == 502 and fc[0].get("failure_type") == "SEND_ERROR", (s, b))
    with mock.patch("django.core.mail.EmailMultiAlternatives.send", return_value=1):
        s, b = post(C, "payments/payment-reminder/", {"project_ids": [project.id]})
    check("payment rows + working mail -> 200", s == 200 and b["data"]["total_emails_sent"] == 1, (s, b))

    # ================= 2. payroll missing attendance
    day_info = lambda d: {"day_type": "WORKING_DAY", "pay_type": "PAID"}
    common = dict(day_info=day_info, records={}, leave_map={}, today=date(2027, 1, 1))
    out = classify_period(date(2026, 12, 1), date(2026, 12, 2), missing_action="ABSENT", **common)
    check("ABSENT: deducted, shown as a note, no review block",
          out["counts"]["absent_days"] == 2 and not out["requires_review"] and not out["warnings"]
          and any("treated as absent" in n for n in out["notes"]), out)
    out = classify_period(date(2026, 12, 1), date(2026, 12, 2), missing_action="REVIEW", **common)
    check("REVIEW still requires review", out["requires_review"] and out["counts"]["absent_days"] == 0, out)
    out = classify_period(date(2026, 12, 1), date(2026, 12, 2), missing_action="SKIP", **common)
    check("SKIP still requires review (paid days)", out["requires_review"], out)

    # ================= 3. super admin and projects
    su = User.objects.create(username="b9_su", email="b9_su@x.test", mobile="9000000102", role=admin_role,
                             is_superuser=True, is_staff=True)
    req = SimpleNamespace(user=su, data={})
    perm, _p, _a, err = get_project_permission(req, project.id)
    check("super admin has no project permission (403)", perm is None and err is not None and err.status_code == 403,
          (perm, getattr(err, "status_code", None)))
    qs, pmap, err = get_accessible_projects(req)
    check("super admin gets no projects in cross-project lists (403 / empty)",
          (err is not None and err.status_code == 403) or (qs is not None and qs.count() == 0 and not pmap),
          (pmap, getattr(err, "status_code", None)))
    S = APIClient()
    S.force_authenticate(user=su)
    s, _ = post(S, "communications/project-chat/messages/", {"project_id": project.id})
    s2, _ = post(S, "projects/task/list/", {"project_id": project.id})
    check("super admin blocked from project chat and tasks", s in (403, 400, 404) and s2 in (403, 400, 404), (s, s2))
    perm, _p, _a, err = get_project_permission(SimpleNamespace(user=owner, data={}), project.id)
    check("organization owner still ADMIN on the project", perm == "ADMIN" and err is None, perm)


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
