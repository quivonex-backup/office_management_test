"""Employees report: headcount list, joiners or exits in a period."""
from datetime import timedelta

from django.db.models import Count

from .common import (
    ReportError, apply_employee_filters, branch_name, build_report, chart, col, dept_name, emp_name,
    employee_scope, parse_period,
)

VIEWS = ("headcount", "joiners", "exits")


def employees_report(request, organization, data, features):
    from app.employees.models import Employee

    ids, scope = employee_scope(request, organization, "employee.view_all", "employee.view_team")
    from_date, to_date = parse_period(data)
    view = str(data.get("view") or "headcount").lower()
    if view not in VIEWS:
        raise ReportError("view must be headcount, joiners or exits.")

    qs = Employee.objects.filter(organization=organization)
    if view == "headcount":
        qs = qs.filter(is_active=True)
    elif view == "joiners":
        qs = qs.filter(joining_date__gte=from_date, joining_date__lte=to_date)
    else:
        qs = qs.filter(resignation_date__gte=from_date, resignation_date__lte=to_date)
    if data.get("employment_status"):
        qs = qs.filter(employment_status=str(data.get("employment_status")).upper())
    if data.get("access_role_id"):
        qs = qs.filter(access_role_id=data.get("access_role_id"))
    if str(data.get("remote_only", "")).lower() in ("true", "1", "yes"):
        qs = qs.filter(attendance_location_exempt=True)
    qs = apply_employee_filters(qs, data, features, prefix="", ids=ids)
    qs = qs.select_related("department_ref", "designation_ref", "branch", "reports_to", "access_role") \
        .order_by("employee_code")

    rows = [{
        "employee_code": e.employee_code, "name": emp_name(e), "department": dept_name(e),
        "designation": e.designation_ref.name if e.designation_ref else (e.designation or None),
        "branch": branch_name(e),
        "joining_date": str(e.joining_date) if e.joining_date else None,
        "exit_date": str(e.resignation_date) if e.resignation_date else None,
        "status": e.get_employment_status_display(),
        "active": e.is_active,
        "reports_to": emp_name(e.reports_to),
        "mobile": e.mobile, "email": e.personal_email,
        "access_role": e.access_role.name if e.access_role else None,
        "remote": bool(e.attendance_location_exempt),
    } for e in qs]

    columns = [
        col("employee_code", "Code"), col("name", "Employee"),
        col("department", "Department", optional=features["has_departments"]),
        col("designation", "Designation", optional="data"),
        col("branch", "Branch", optional=features["has_branches"]),
        col("joining_date", "Joining date", "date"),
        col("exit_date", "Exit date", "date", optional=True if view == "exits" else "data"),
        col("status", "Status"), col("active", "Active", "bool", optional=view != "headcount"),
        col("reports_to", "Reports to", optional="data"),
        col("mobile", "Mobile", optional="data"), col("email", "Email", optional="data"),
        col("access_role", "Access role", optional="data"),
        col("remote", "Remote", "bool", optional=features["has_remote"]),
    ]

    filters = {"from_date": str(from_date), "to_date": str(to_date), "view": view, "scope": scope}
    for k in ("employment_status", "access_role_id", "remote_only", "employee_id", "department_id", "branch_id",
              "designation_id", "search"):
        if data.get(k):
            filters[k] = data.get(k)

    # Chart: headcount by department (or designation); joiners vs exits per month in the period
    base = Employee.objects.filter(organization=organization)
    if ids is not None:
        base = base.filter(id__in=ids)
    if view == "headcount":
        group = "department_ref__name" if features["has_departments"] else "designation_ref__name"
        agg = base.filter(is_active=True).values(group).annotate(n=Count("id")).order_by("-n")
        chart_data = chart("bar", [a[group] or "Not set" for a in agg],
                           [{"name": "Employees", "data": [a["n"] for a in agg]}])
    else:
        months, d = [], from_date.replace(day=1)
        while d <= to_date:
            months.append(d)
            d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        joined = [base.filter(joining_date__year=m.year, joining_date__month=m.month).count() for m in months]
        left = [base.filter(resignation_date__year=m.year, resignation_date__month=m.month).count() for m in months]
        chart_data = chart("line", [m.strftime("%b %Y") for m in months],
                           [{"name": "Joiners", "data": joined}, {"name": "Exits", "data": left}])

    titles = {"headcount": "Employees (headcount)", "joiners": "Joiners", "exits": "Exits"}
    period = "" if view == "headcount" else f" {from_date:%d %b %Y} - {to_date:%d %b %Y}"
    return build_report(
        key="employees", title=f"{titles[view]}{period}", filters=filters, columns=columns, rows=rows,
        chart_data=chart_data, extra={"summary": {"employees": len(rows)}},
    )
