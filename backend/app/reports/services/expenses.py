"""Expenses report: employee reimbursements, or company expenses (one-off + recurring entries)."""
from datetime import date

from common.permissions import has_perm

from .common import (
    ReportError, apply_employee_filters, build_report, chart, col, dept_name, emp_name, num, parse_period,
)

REIMBURSEMENT_CODES = ("reimbursement.review", "reimbursement.pay")
REIMBURSEMENT_STATUSES = ("PENDING", "APPROVED", "REJECTED", "PAID", "CANCELLED")


def _user_name(user):
    if not user:
        return None
    return f"{user.first_name} {user.last_name}".strip() or user.username


def _by_category_chart(rows, labels_map):
    totals = {}
    for r in rows:
        totals[r["category"]] = totals.get(r["category"], 0) + (r["amount"] or 0)
    ordered = sorted(totals.items(), key=lambda kv: -kv[1])
    return chart("bar", [k for k, _v in ordered], [{"name": "Amount", "data": [round(v, 2) for _k, v in ordered]}])


def expenses_report(request, organization, data, features):
    from app.expenses.models import EmployeeReimbursement, Expense, RecurringExpenseEntry

    can_reimb = any(has_perm(request, organization, c) for c in REIMBURSEMENT_CODES)
    can_company = has_perm(request, organization, "expense.manage")
    default_view = "reimbursements" if can_reimb else "company"
    view = str(data.get("view") or default_view).lower()
    if view not in ("reimbursements", "company"):
        raise ReportError("view must be reimbursements or company.")
    if view == "reimbursements" and not can_reimb:
        raise ReportError("You do not have permission to view reimbursements.", http_status=403)
    if view == "company" and not can_company:
        raise ReportError("You do not have permission to view company expenses.", http_status=403)

    from_date, to_date = parse_period(data)
    labels_map = dict(Expense.EXPENSE_TYPE_CHOICES)
    category = str(data.get("category") or "").lower() or None
    if category and category not in labels_map:
        raise ReportError(f"category must be one of {', '.join(labels_map)}.")
    filters = {"from_date": str(from_date), "to_date": str(to_date), "view": view}
    for k in ("category", "status", "payment_status", "vendor_id", "project_id", "employee_id", "department_id",
              "branch_id", "search"):
        if data.get(k):
            filters[k] = data.get(k)

    if view == "reimbursements":
        status = str(data.get("status") or "").upper() or None
        if status and status not in REIMBURSEMENT_STATUSES:
            raise ReportError(f"status must be one of {', '.join(REIMBURSEMENT_STATUSES)}.")
        qs = EmployeeReimbursement.objects.filter(organization=organization, is_active=True,
                                                  expense_date__gte=from_date, expense_date__lte=to_date)
        if status:
            qs = qs.filter(status=status)
        if category:
            qs = qs.filter(expense_type=category)
        if data.get("project_id"):
            qs = qs.filter(project_id=data.get("project_id"))
        qs = apply_employee_filters(qs, data, features) \
            .select_related("employee", "employee__department_ref", "project", "reviewed_by") \
            .order_by("expense_date", "id")
        rows = [{
            "number": r.reimbursement_number, "expense_date": str(r.expense_date),
            "employee_code": r.employee.employee_code, "name": emp_name(r.employee),
            "department": dept_name(r.employee),
            "category": labels_map.get(r.expense_type, r.expense_type), "title": r.title,
            "project": r.project.project_name if r.project else None,
            "amount": num(r.amount), "status": r.get_status_display(),
            "reviewed_by": _user_name(r.reviewed_by),
            "payment_date": str(r.payment_date) if r.payment_date else None,
        } for r in qs]
        columns = [
            col("number", "Number"), col("expense_date", "Date", "date"), col("employee_code", "Code"),
            col("name", "Employee"), col("department", "Department", optional=features["has_departments"]),
            col("category", "Category"), col("title", "Title"), col("project", "Project", optional="data"),
            col("amount", "Amount", "money"), col("status", "Status"),
            col("reviewed_by", "Reviewed by", optional="data"), col("payment_date", "Paid on", "date", optional="data"),
        ]
        by_status = {}
        for r in rows:
            by_status[r["status"]] = round(by_status.get(r["status"], 0) + r["amount"], 2)
        return build_report(
            key="expenses", title=f"Reimbursements {from_date:%d %b %Y} - {to_date:%d %b %Y}",
            filters=filters, columns=columns, rows=rows,
            totals={"amount": round(sum(r["amount"] for r in rows), 2)},
            chart_data=_by_category_chart(rows, labels_map),
            extra={"summary": {"claims": len(rows), "amount_by_status": by_status}},
        )

    # ---- company: one-off expenses + recurring entries in the period
    payment_status = str(data.get("payment_status") or "").lower() or None
    if payment_status and payment_status not in ("paid", "unpaid"):
        raise ReportError("payment_status must be paid or unpaid.")
    exp = Expense.objects.filter(organization=organization, is_active=True,
                                 expense_date__gte=from_date, expense_date__lte=to_date)
    entries = RecurringExpenseEntry.objects.filter(recurring_expense__organization=organization, is_active=True,
                                                   recurring_expense__is_active=True)
    if category:
        exp = exp.filter(expense_type=category)
        entries = entries.filter(recurring_expense__expense_type=category)
    if payment_status:
        exp = exp.filter(payment_status=payment_status)
        entries = entries.filter(payment_status=payment_status)
    if data.get("vendor_id"):
        exp = exp.filter(vendor_id=data.get("vendor_id"))
        entries = entries.filter(recurring_expense__vendor_id=data.get("vendor_id"))
    if data.get("project_id"):
        exp = exp.filter(project_id=data.get("project_id"))
        entries = entries.filter(recurring_expense__project_id=data.get("project_id"))
    search = (data.get("search") or "").strip().lower()

    rows = []
    for e in exp.select_related("vendor", "project"):
        rows.append({
            "date": str(e.expense_date), "number": e.expense_number, "source": "One-off",
            "category": labels_map.get(e.expense_type, e.expense_type), "title": e.title,
            "vendor": e.vendor.vendor_name if e.vendor else None,
            "project": e.project.project_name if e.project else None,
            "amount": num(e.amount), "due_date": str(e.due_date) if e.due_date else None,
            "payment_status": e.get_payment_status_display(),
            "payment_date": str(e.payment_date) if e.payment_date else None,
        })
    for en in entries.select_related("recurring_expense", "recurring_expense__vendor", "recurring_expense__project"):
        day = en.due_date or date(en.year, en.month, 1)
        if not (from_date <= day <= to_date):
            continue
        rec = en.recurring_expense
        rows.append({
            "date": str(day), "number": None, "source": f"Recurring ({rec.get_frequency_display()})",
            "category": labels_map.get(rec.expense_type, rec.expense_type), "title": rec.title,
            "vendor": rec.vendor.vendor_name if rec.vendor else None,
            "project": rec.project.project_name if rec.project else None,
            "amount": num(en.amount), "due_date": str(en.due_date) if en.due_date else None,
            "payment_status": en.get_payment_status_display(),
            "payment_date": str(en.payment_date) if en.payment_date else None,
        })
    if search:
        rows = [r for r in rows if search in (r["title"] or "").lower() or search in (r["vendor"] or "").lower()
                or search in (r["number"] or "").lower()]
    rows.sort(key=lambda r: (r["date"], r["title"] or ""))
    columns = [
        col("date", "Date", "date"), col("number", "Number", optional="data"), col("source", "Type"),
        col("category", "Category"), col("title", "Title"), col("vendor", "Vendor", optional="data"),
        col("project", "Project", optional="data"), col("amount", "Amount", "money"),
        col("due_date", "Due date", "date", optional="data"), col("payment_status", "Payment"),
        col("payment_date", "Paid on", "date", optional="data"),
    ]
    unpaid = round(sum(r["amount"] for r in rows if r["payment_status"] == "Unpaid"), 2)
    return build_report(
        key="expenses", title=f"Company expenses {from_date:%d %b %Y} - {to_date:%d %b %Y}",
        filters=filters, columns=columns, rows=rows,
        totals={"amount": round(sum(r["amount"] for r in rows), 2)},
        chart_data=_by_category_chart(rows, labels_map),
        extra={"summary": {"entries": len(rows), "unpaid": unpaid}},
    )
