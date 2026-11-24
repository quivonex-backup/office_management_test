"""Leave report: leave taken in a period, or balances (calendar leave year)."""
from decimal import Decimal

from django.db.models import Q

from .common import (
    ReportError, apply_employee_filters, branch_name, build_report, chart, col, dept_name, emp_name,
    employee_scope, num, parse_period,
)

STATUSES = ("PENDING", "APPROVED", "REJECTED", "CANCELLED")


def leave_report(request, organization, data, features):
    from app.employees.models import Employee
    from app.leave.models import EmployeeLeaveBalance, LeaveApplication, LeaveType

    ids, scope = employee_scope(request, organization, "leave.view_all", "leave.view_team")
    from_date, to_date = parse_period(data)
    view = str(data.get("view") or "taken").lower()
    if view not in ("taken", "balance"):
        raise ReportError("view must be taken or balance.")
    status = str(data.get("status") or "").upper() or None
    if status and status not in STATUSES:
        raise ReportError(f"status must be one of {', '.join(STATUSES)}.")

    types = LeaveType.objects.filter(organization=organization, is_active=True).order_by("name")
    if data.get("leave_type_id"):
        types = types.filter(id=data.get("leave_type_id"))
    types = list(types)

    filters = {"from_date": str(from_date), "to_date": str(to_date), "view": view, "scope": scope}
    for k in ("status", "leave_type_id", "employee_id", "department_id", "branch_id", "designation_id", "search"):
        if data.get(k):
            filters[k] = data.get(k)

    if view == "balance":
        year = to_date.year
        filters["leave_year"] = year
        emps = Employee.objects.filter(organization=organization, is_active=True)
        emps = apply_employee_filters(emps, data, features, prefix="", ids=ids) \
            .select_related("department_ref", "branch").order_by("employee_code")
        balances = {}
        for b in EmployeeLeaveBalance.objects.filter(organization=organization, leave_year=year,
                                                     leave_type__in=types, employee__in=emps):
            balances[(b.employee_id, b.leave_type_id)] = b
        rows = []
        for e in emps:
            row = {"employee_code": e.employee_code, "name": emp_name(e), "department": dept_name(e),
                   "branch": branch_name(e)}
            for t in types:
                b = balances.get((e.id, t.id))
                row[f"{t.code}_allocated"] = num(b.opening_balance + b.allocated_days) if b else 0
                row[f"{t.code}_used"] = num(b.used_days) if b else 0
                row[f"{t.code}_pending"] = num(b.pending_days) if b else 0
                row[f"{t.code}_available"] = num(b.available) if b else 0
            rows.append(row)
        columns = [col("employee_code", "Code"), col("name", "Employee"),
                   col("department", "Department", optional=features["has_departments"]),
                   col("branch", "Branch", optional=features["has_branches"])]
        totals = {}
        for t in types:
            for part, label in (("allocated", "allocated"), ("used", "used"), ("pending", "pending"),
                                ("available", "available")):
                key = f"{t.code}_{part}"
                columns.append(col(key, f"{t.name} {label}", "number",
                                   optional="data" if part == "pending" else None))
                totals[key] = round(sum(r[key] for r in rows), 2)
        return build_report(
            key="leave", title=f"Leave balance {year}", filters=filters, columns=columns, rows=rows, totals=totals,
            chart_data=chart("bar", [t.name for t in types], [
                {"name": "Used", "data": [totals[f"{t.code}_used"] for t in types]},
                {"name": "Available", "data": [totals[f"{t.code}_available"] for t in types]},
            ]),
        )

    apps = LeaveApplication.objects.filter(organization=organization, leave_type__in=types,
                                           start_date__lte=to_date, end_date__gte=from_date)
    if status:
        apps = apps.filter(status=status)
    apps = apply_employee_filters(apps, data, features, ids=ids) \
        .select_related("employee", "employee__department_ref", "employee__branch", "leave_type", "reviewed_by") \
        .order_by("start_date", "employee__employee_code")
    rows = []
    for a in apps:
        reviewer = a.reviewed_by
        rows.append({
            "employee_code": a.employee.employee_code, "name": emp_name(a.employee),
            "department": dept_name(a.employee), "branch": branch_name(a.employee),
            "leave_type": a.leave_type.name, "paid": a.leave_type.is_paid,
            "from": str(a.start_date), "to": str(a.end_date), "days": num(a.total_days),
            "status": a.get_status_display(),
            "applied_on": a.created_at.date().isoformat(),
            "reviewed_by": ((f"{reviewer.first_name} {reviewer.last_name}".strip() or reviewer.username)
                            if reviewer else None),
            "reason": a.reason,
        })
    columns = [
        col("employee_code", "Code"), col("name", "Employee"),
        col("department", "Department", optional=features["has_departments"]),
        col("branch", "Branch", optional=features["has_branches"]),
        col("leave_type", "Leave type"), col("paid", "Paid", "bool"), col("from", "From", "date"),
        col("to", "To", "date"), col("days", "Days", "number"), col("status", "Status"),
        col("applied_on", "Applied on", "date"), col("reviewed_by", "Reviewed by", optional="data"),
        col("reason", "Reason"),
    ]
    approved = [r for r in rows if r["status"] == "Approved"]
    per_type = {t.name: Decimal("0") for t in types}
    for r in approved:
        per_type[r["leave_type"]] = per_type.get(r["leave_type"], Decimal("0")) + Decimal(str(r["days"]))
    return build_report(
        key="leave", title=f"Leave taken {from_date:%d %b %Y} - {to_date:%d %b %Y}",
        filters=filters, columns=columns, rows=rows,
        totals={"days": round(sum(r["days"] for r in rows), 2)},
        chart_data=chart("bar", list(per_type.keys()),
                         [{"name": "Approved days", "data": [float(v) for v in per_type.values()]}]),
        extra={"summary": {"applications": len(rows), "approved_days": round(sum(r["days"] for r in approved), 2),
                           "pending": sum(1 for r in rows if r["status"] == "Pending")}},
    )
