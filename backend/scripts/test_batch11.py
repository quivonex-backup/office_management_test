"""
Batch 11 checks: reports employees / expenses / receivables / projects /
helpdesk (json + xlsx, permissions, scope) and Excel on visitors / assets lists.

Run after migrate; any database; everything is rolled back:
    python manage.py shell -c "exec(open('scripts/test_batch11.py').read())"
"""
import sys
import traceback
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import BytesIO

from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from app.accounts.models import AccessRole, Organization, OrganizationMembership, Role, User
from app.accounts.services import seed_organization_defaults
from app.assets.models import Asset, AssetCategory
from app.clients.models import Client
from app.employees.models import Department, Employee
from app.expenses.models import EmployeeReimbursement, Expense, RecurringExpense, RecurringExpenseEntry
from app.helpdesk.models import Ticket, TicketCategory, TicketComment
from app.payments.models import ProjectPayment, ProjectPaymentTransaction
from app.projects.models import Project, ProjectTeamAllocation, Task
from app.visitors.models import Visit

RESULTS = []
D = Decimal
OCT1, OCT31 = date(2026, 10, 1), date(2026, 10, 31)
RNG = {"from_date": str(OCT1), "to_date": str(OCT31)}


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
        return r.status_code, r
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.content[:200]}


def xlsx_header(resp):
    from openpyxl import load_workbook
    ws = load_workbook(BytesIO(resp.content)).active
    return [c.value for c in ws[5] if c.value]


def aware(day, hh=10, mm=0):
    return timezone.make_aware(datetime.combine(day, time(hh, mm)))


def with_extra(model, **kw):
    fields = {f.name for f in model._meta.get_fields()}
    return {k: v for k, v in kw.items() if k in fields}


def run():
    admin_role, _ = Role.objects.get_or_create(name="Admin", defaults={"is_active": True})
    emp_role, _ = Role.objects.get_or_create(name="Employee", defaults={"is_active": True})
    n = [0]

    def user(name, role=emp_role):
        n[0] += 1
        return User.objects.create(username=f"b11_{name}", email=f"b11_{name}@x.test", mobile=f"11000000{n[0]:02d}",
                                   role=role, first_name=name.title())

    owner = user("owner", admin_role)
    org = Organization.objects.create(organization_name="B11 Org", owner=owner, email="hr@b11.test")
    OrganizationMembership.objects.create(organization=org, user=owner, is_active=True)
    seed_organization_defaults(org)
    roles = {r.name: r for r in AccessRole.objects.filter(organization=org)}
    it = Department.objects.create(organization=org, name="IT")

    def employee(name, role=None, **kw):
        u = user(name)
        OrganizationMembership.objects.create(organization=org, user=u, is_active=True)
        return Employee.objects.create(organization=org, first_name=name.title(), last_name="T",
                                       employee_code=f"B11-{name}", user=u, access_role=role,
                                       employment_status="ACTIVE", **kw)

    hr = employee("hr", roles["HR Manager"], joining_date=date(2025, 1, 1))
    pm = employee("pay", roles["Payroll Manager"], joining_date=date(2025, 1, 1))
    mgr = employee("mgr", roles["Department Manager"], joining_date=date(2025, 1, 1))
    dev = employee("dev", reports_to=mgr, joining_date=date(2026, 10, 15), department_ref=it)
    plain = employee("plain", joining_date=date(2026, 9, 1))
    left = employee("left", joining_date=date(2024, 5, 1))
    Employee.objects.filter(pk=left.pk).update(is_active=False, employment_status="RESIGNED",
                                               resignation_date=date(2026, 10, 20))
    C = {k: client_for(v.user) for k, v in dict(hr=hr, pay=pm, mgr=mgr, dev=dev, plain=plain).items()}
    C["owner"] = client_for(owner)

    s, b = post(C["owner"], "reports/list/")
    keys = [r["key"] for r in b["data"]["reports"]]
    check("owner sees all 9 reports", len(keys) == 9 and {"employees", "expenses", "receivables", "projects",
                                                          "helpdesk"} <= set(keys), keys)
    s, b = post(C["hr"], "reports/list/")
    check("HR manager: + employees, expenses, helpdesk (not receivables / projects)",
          {"employees", "expenses", "helpdesk"} <= {r["key"] for r in b["data"]["reports"]}
          and not {"receivables", "projects"} & {r["key"] for r in b["data"]["reports"]},
          [r["key"] for r in b["data"]["reports"]])

    # ================= EMPLOYEES
    s, b = post(C["hr"], "reports/employees/")
    codes = {r["employee_code"] for r in b["data"]["rows"]}
    check("headcount = active employees", s == 200 and "B11-left" not in codes and "B11-dev" in codes
          and len(codes) == 5, codes)
    s, b = post(C["hr"], "reports/employees/", {**RNG, "view": "joiners"})
    check("joiners in October", s == 200 and [r["employee_code"] for r in b["data"]["rows"]] == ["B11-dev"], b)
    s, b = post(C["hr"], "reports/employees/", {**RNG, "view": "exits"})
    cols = [c["key"] for c in b["data"]["columns"]]
    check("exits in October (with exit date column)", [r["employee_code"] for r in b["data"]["rows"]] == ["B11-left"]
          and "exit_date" in cols and b["data"]["chart"]["type"] == "line", (b["data"]["rows"], cols))
    s, b = post(C["mgr"], "reports/employees/")
    codes = {r["employee_code"] for r in b["data"]["rows"]}
    check("team scope for employee.view_team", s == 200 and codes == {"B11-mgr", "B11-dev"}, codes)
    s, _ = post(C["plain"], "reports/employees/")
    check("plain employee -> 403", s == 403, s)

    # ================= EXPENSES
    EmployeeReimbursement.objects.create(organization=org, employee=dev, reimbursement_number="RB-1", title="Cab",
                                         expense_type="travel", amount=D("450"), expense_date=date(2026, 10, 9),
                                         status="APPROVED")
    EmployeeReimbursement.objects.create(organization=org, employee=plain, reimbursement_number="RB-2", title="Lunch",
                                         expense_type="food", amount=D("300"), expense_date=date(2026, 10, 10))
    Expense.objects.create(organization=org, expense_number="EX-1", title="AWS", expense_type="cloud",
                           amount=D("12000"), expense_date=date(2026, 10, 3), payment_status="paid")
    rex = RecurringExpense.objects.create(organization=org, title="Office rent", expense_type="rent",
                                          start_date=date(2026, 1, 1))
    RecurringExpenseEntry.objects.create(recurring_expense=rex, year=2026, month=10, amount=D("50000"),
                                         due_date=date(2026, 10, 5))
    RecurringExpenseEntry.objects.create(recurring_expense=rex, year=2026, month=11, amount=D("50000"),
                                         due_date=date(2026, 11, 5))
    s, b = post(C["hr"], "reports/expenses/", RNG)
    check("reimbursement reviewer: default view reimbursements", s == 200 and b["data"]["filters"]["view"] == "reimbursements"
          and b["data"]["totals"]["amount"] == 750.0 and len(b["data"]["rows"]) == 2, b)
    s, b = post(C["hr"], "reports/expenses/", {**RNG, "view": "company"})
    check("company expenses need expense.manage", s == 403, s)
    s, b = post(C["pay"], "reports/expenses/", {**RNG, "view": "company"})
    check("company expenses = one-off + recurring entries in the period",
          s == 200 and b["data"]["totals"]["amount"] == 62000.0 and len(b["data"]["rows"]) == 2
          and b["data"]["summary"]["unpaid"] == 50000.0, b.get("data", {}).get("rows"))
    s, b = post(C["pay"], "reports/expenses/", {**RNG, "view": "company", "category": "rent"})
    check("category filter", s == 200 and [r["title"] for r in b["data"]["rows"]] == ["Office rent"], b)
    s, b = post(C["hr"], "reports/expenses/", {**RNG, "category": "nope"})
    check("bad category -> 400", s == 400, s)

    # ================= RECEIVABLES
    client = Client.objects.create(organization=org, client_code="B11-C", client_name="ABC Tech")
    project = Project.objects.create(organization=org, client=client, project_code="B11-P", project_name="Portal",
                                     total_cost=D("300000"), status="in_progress")
    extra = with_extra(ProjectPayment, organization=org)
    today = timezone.localdate()
    p1 = ProjectPayment.objects.create(project=project, payment_type="ADVANCE", amount=D("100000"),
                                       paid_amount=D("60000"), outstanding_amount=D("40000"),
                                       due_date=date(2026, 10, 10), status="PARTIALLY_PAID", **extra)
    ProjectPayment.objects.create(project=project, payment_type="INSTALLMENT", installment_number=1,
                                  amount=D("100000"), outstanding_amount=D("100000"),
                                  due_date=today - timedelta(days=75), status="OVERDUE", **extra)
    ProjectPaymentTransaction.objects.create(payment=p1, amount=D("60000"), payment_method="UPI",
                                             transaction_date=date(2026, 10, 12), status="SUCCESS",
                                             **with_extra(ProjectPaymentTransaction, organization=org))
    s, b = post(C["hr"], "reports/receivables/", RNG)
    check("receivables need payment.manage", s == 403, s)
    s, b = post(C["owner"], "reports/receivables/", RNG)
    row = b["data"]["rows"][0] if s == 200 and b["data"]["rows"] else {}
    check("receivables due in October with last payment + collected in period",
          s == 200 and row.get("outstanding") == 40000.0 and row.get("last_payment_date") == "2026-10-12"
          and b["data"]["summary"]["collected_in_period"] == 60000.0, b.get("data"))
    s, b = post(C["owner"], "reports/receivables/", {"overdue_only": True})
    ageing = b["data"]["summary"]["ageing_days"]
    check("overdue_only + ageing buckets", s == 200 and any(r["days_overdue"] >= 61 for r in b["data"]["rows"])
          and ageing["61-90"] == 100000.0, (ageing, [r["days_overdue"] for r in b["data"]["rows"]]))

    # ================= PROJECTS
    ProjectTeamAllocation.objects.create(project=project, employee=mgr, is_project_head=True)
    Task.objects.create(project=project, organization=org, title="API", status="DONE", assigned_to=dev,
                        completed_at=aware(date(2026, 10, 20)))
    Task.objects.create(project=project, organization=org, title="UI", status="IN_PROGRESS", assigned_to=dev,
                        due_date=today - timedelta(days=2))
    Task.objects.create(project=project, organization=org, title="Docs", status="TODO", assigned_to=plain)
    s, b = post(C["owner"], "reports/projects/", RNG)
    row = b["data"]["rows"][0] if s == 200 else {}
    check("projects: tasks done / open / overdue, % complete, head",
          row.get("total_tasks") == 3 and row.get("done_tasks") == 1 and row.get("overdue_tasks") == 1
          and row.get("done_in_period") == 1 and row.get("percent_complete") == 33.3 and row.get("heads") == "Mgr T",
          row)
    s, b = post(C["owner"], "reports/projects/", {**RNG, "view": "assignees"})
    first = b["data"]["rows"][0] if s == 200 else {}
    check("assignees view sorted by overdue", first.get("employee_code") == "B11-dev" and first.get("overdue_tasks") == 1
          and first.get("done_in_period") == 1, b.get("data", {}).get("rows"))
    s, _ = post(C["hr"], "reports/projects/", RNG)
    check("projects report needs project.manage", s == 403, s)

    # ================= HELPDESK
    cat_it = TicketCategory.objects.create(organization=org, name="IT", department=it)
    cat_hr = TicketCategory.objects.create(organization=org, name="Payroll")
    t1 = Ticket.objects.create(organization=org, ticket_code="T-1", category=cat_it, raised_by=plain, subject="Laptop",
                               description="x", status="RESOLVED", assigned_to=dev)
    t2 = Ticket.objects.create(organization=org, ticket_code="T-2", category=cat_hr, raised_by=dev, subject="Payslip",
                               description="y")
    Ticket.objects.filter(pk=t1.pk).update(created_at=aware(date(2026, 10, 5), 10), resolved_at=aware(date(2026, 10, 5), 16))
    Ticket.objects.filter(pk=t2.pk).update(created_at=aware(date(2026, 10, 7), 9))
    TicketComment.objects.create(ticket=t1, message="Status changed from Resolved to Open.", is_system=True)
    s, b = post(C["hr"], "reports/helpdesk/", RNG)
    rows = {r["ticket_code"]: r for r in b["data"]["rows"]} if s == 200 else {}
    check("tickets: resolution hours, reopened, open days",
          rows.get("T-1", {}).get("resolution_hours") == 6.0 and rows.get("T-1", {}).get("reopened") is True
          and rows.get("T-2", {}).get("open_days") is not None and b["data"]["summary"]["tickets"] == 2, rows)
    s, b = post(C["hr"], "reports/helpdesk/", {**RNG, "view": "summary"})
    cats = {r["category"]: r for r in b["data"]["rows"]} if s == 200 else {}
    check("summary per category", cats.get("IT", {}).get("resolved") == 1
          and cats.get("IT", {}).get("average_resolution_hours") == 6.0 and cats.get("Payroll", {}).get("open_now") == 1,
          cats)
    handler_role = AccessRole.objects.create(organization=org, name="IT desk")
    from app.accounts.models import Permission
    handler_role.permissions.add(Permission.objects.get(code="ticket.handle"))
    Employee.objects.filter(pk=dev.pk).update(access_role=handler_role)
    s, b = post(C["dev"], "reports/helpdesk/", RNG)
    check("handler sees only own department's tickets", s == 200
          and [r["ticket_code"] for r in b["data"]["rows"]] == ["T-1"], b)

    # ================= EXCEL for every new report + lists
    ok = True
    for url, who, extra in (("employees", "hr", {}), ("expenses", "pay", {"view": "company"}),
                            ("receivables", "owner", {}), ("projects", "owner", {}), ("helpdesk", "hr", {})):
        s, r = post(C[who], f"reports/{url}/", {**RNG, **extra, "format": "xlsx"})
        ok = ok and s == 200 and hasattr(r, "content") and r.content[:2] == b"PK"
    check("Excel download for all 5 new reports", ok)

    Visit.objects.create(organization=org, visit_code="V-1", visitor_name="Ravi", visitor_mobile="9876500011",
                         purpose="MEETING", host=dev, check_in_at=timezone.now(), id_proof_type="PAN",
                         id_proof_last4="123F")
    s, r = post(C["hr"], "visitors/visit/list/", {"format": "xlsx"})
    header = xlsx_header(r) if s == 200 and hasattr(r, "content") else []
    check("visitor log Excel (no branch column without branches)", header[:4] == ["Visit", "Check-in", "Check-out", "Visitor"]
          and "Branch" not in header, (s, header))
    cat = AssetCategory.objects.create(organization=org, name="Laptop")
    Asset.objects.create(organization=org, asset_code="AST-1", category=cat, name="Dell", serial_number="SN1",
                         status="ASSIGNED", current_holder=dev)
    s, r = post(C["hr"], "assets/asset/list/", {"format": "xlsx"})
    header = xlsx_header(r) if s == 200 and hasattr(r, "content") else []
    check("asset register Excel hides empty columns", "Serial" in header and "Cost" not in header
          and "Holder" in header, (s, header))
    s, b = post(C["hr"], "assets/asset/list/")
    check("asset list JSON unchanged without format", s == 200 and b["summary"]["total"] == 1, b)


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
