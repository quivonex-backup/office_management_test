"""Attendance report: summary (one row per employee) or daily (one row per day)."""
from django.db.models import Count, Q, Sum

from .common import (
    ReportError, apply_employee_filters, branch_name, build_report, chart, col, days_between, dept_name,
    emp_name, employee_scope, fmt_time, minutes_to_hours, parse_period,
)

DAILY_STATUSES = ("PRESENT", "HALF_DAY", "ABSENT", "ON_LEAVE", "INCOMPLETE", "PENDING_REVIEW", "HOLIDAY", "WEEKLY_OFF")
WORKED = ("PRESENT", "HALF_DAY", "INCOMPLETE", "PENDING_REVIEW")


def attendance_report(request, organization, data, features):
    from app.attendance.models import AttendanceRecord
    from app.employees.models import Employee

    ids, scope = employee_scope(request, organization, "attendance.view_all", "attendance.view_team")
    from_date, to_date = parse_period(data)
    view = str(data.get("view") or "summary").lower()
    if view not in ("summary", "daily"):
        raise ReportError("view must be summary or daily.")

    status = str(data.get("status") or "").upper() or None
    if status and status not in DAILY_STATUSES:
        raise ReportError(f"status must be one of {', '.join(DAILY_STATUSES)}.")
    late_only = str(data.get("late_only", "")).lower() in ("true", "1", "yes")
    early_only = str(data.get("early_only", "")).lower() in ("true", "1", "yes")
    ot_only = str(data.get("overtime_only", "")).lower() in ("true", "1", "yes")

    filters = {"from_date": str(from_date), "to_date": str(to_date), "view": view, "scope": scope}
    for k in ("status", "employee_id", "department_id", "branch_id", "designation_id", "search"):
        if data.get(k):
            filters[k] = data.get(k)
    for k, v in (("late_only", late_only), ("early_only", early_only), ("overtime_only", ot_only)):
        if v:
            filters[k] = True

    recs = AttendanceRecord.objects.filter(organization=organization, work_date__gte=from_date,
                                           work_date__lte=to_date)
    recs = apply_employee_filters(recs, data, features, ids=ids)
    ot_col = features["overtime_enabled"]

    if view == "daily":
        if status:
            recs = recs.filter(status=status)
        if late_only:
            recs = recs.filter(late_minutes__gt=0)
        if early_only:
            recs = recs.filter(early_departure_minutes__gt=0)
        if ot_only:
            recs = recs.filter(overtime_minutes__gt=0)
        recs = recs.select_related("employee", "employee__department_ref", "employee__branch", "shift") \
            .order_by("work_date", "employee__employee_code")
        rows = [{
            "work_date": str(r.work_date),
            "employee_code": r.employee.employee_code,
            "name": emp_name(r.employee),
            "department": dept_name(r.employee),
            "branch": branch_name(r.employee),
            "shift": r.shift.name if r.shift else None,
            "check_in": fmt_time(r.check_in),
            "check_out": fmt_time(r.check_out),
            "status": r.get_status_display(),
            "late_minutes": r.late_minutes,
            "early_minutes": r.early_departure_minutes,
            "overtime_minutes": r.overtime_minutes,
            "worked_hours": minutes_to_hours(r.net_work_minutes) if r.check_out else None,
            "remote": bool(r.employee.attendance_location_exempt),
        } for r in recs]
        columns = [
            col("work_date", "Date", "date"), col("employee_code", "Code"), col("name", "Employee"),
            col("department", "Department", optional=features["has_departments"]),
            col("branch", "Branch", optional=features["has_branches"]),
            col("shift", "Shift", optional="data"), col("check_in", "Check-in", "time"),
            col("check_out", "Check-out", "time"), col("status", "Status"),
            col("late_minutes", "Late (min)", "number"), col("early_minutes", "Early (min)", "number"),
            col("overtime_minutes", "OT (min)", "number", optional=ot_col),
            col("worked_hours", "Worked (h)", "number"),
            col("remote", "Remote", "bool", optional=features["has_remote"]),
        ]
        per_day = {}
        for r in rows:
            d = per_day.setdefault(r["work_date"], {"n": 0, "late": 0})
            d["n"] += 1
            d["late"] += 1 if r["late_minutes"] else 0
        labels = [str(d) for d in days_between(from_date, to_date)]
        title_status = f" - {dict(AttendanceRecord.STATUS_CHOICES).get(status, status)}" if status else ""
        return build_report(
            key="attendance", title=f"Daily attendance{title_status} {from_date:%d %b %Y} - {to_date:%d %b %Y}",
            filters=filters, columns=columns, rows=rows,
            totals={"late_minutes": sum(r["late_minutes"] for r in rows),
                    "early_minutes": sum(r["early_minutes"] for r in rows),
                    "overtime_minutes": sum(r["overtime_minutes"] for r in rows)},
            chart_data=chart("line", labels, [
                {"name": "Records", "data": [per_day.get(d, {}).get("n", 0) for d in labels]},
                {"name": "Late", "data": [per_day.get(d, {}).get("late", 0) for d in labels]},
            ]),
        )

    # ---- summary: one row per employee (active employees in scope, even without records)
    agg = {
        r["employee_id"]: r for r in recs.values("employee_id").annotate(
            present=Count("id", filter=Q(status="PRESENT")),
            half_days=Count("id", filter=Q(status="HALF_DAY")),
            absent=Count("id", filter=Q(status="ABSENT")),
            on_leave=Count("id", filter=Q(status="ON_LEAVE")),
            incomplete=Count("id", filter=Q(status__in=("INCOMPLETE", "PENDING_REVIEW"))),
            late_days=Count("id", filter=Q(late_minutes__gt=0)),
            late_minutes=Sum("late_minutes"),
            early_minutes=Sum("early_departure_minutes"),
            overtime_minutes=Sum("overtime_minutes"),
            worked_minutes=Sum("net_work_minutes", filter=Q(check_out__isnull=False)),
        )
    }
    emps = Employee.objects.filter(organization=organization).filter(
        Q(is_active=True) | Q(id__in=list(agg.keys())))
    emps = apply_employee_filters(emps, data, features, prefix="", ids=ids) \
        .select_related("department_ref", "branch").order_by("employee_code")
    rows = []
    for e in emps:
        a = agg.get(e.id, {})
        row = {
            "employee_code": e.employee_code, "name": emp_name(e), "department": dept_name(e),
            "branch": branch_name(e),
            "present": a.get("present", 0), "half_days": a.get("half_days", 0), "absent": a.get("absent", 0),
            "on_leave": a.get("on_leave", 0), "incomplete": a.get("incomplete", 0),
            "late_days": a.get("late_days", 0), "late_minutes": a.get("late_minutes") or 0,
            "early_minutes": a.get("early_minutes") or 0,
            "overtime_hours": minutes_to_hours(a.get("overtime_minutes") or 0),
            "worked_hours": minutes_to_hours(a.get("worked_minutes") or 0),
            "remote": bool(e.attendance_location_exempt),
        }
        if status == "ABSENT" and not row["absent"]:
            continue
        if status == "HALF_DAY" and not row["half_days"]:
            continue
        if status == "ON_LEAVE" and not row["on_leave"]:
            continue
        if late_only and not row["late_days"]:
            continue
        if early_only and not row["early_minutes"]:
            continue
        if ot_only and not row["overtime_hours"]:
            continue
        rows.append(row)
    columns = [
        col("employee_code", "Code"), col("name", "Employee"),
        col("department", "Department", optional=features["has_departments"]),
        col("branch", "Branch", optional=features["has_branches"]),
        col("present", "Present", "number"), col("half_days", "Half days", "number"),
        col("absent", "Absent", "number"), col("on_leave", "On leave", "number"),
        col("incomplete", "Incomplete", "number", optional="data"),
        col("late_days", "Late days", "number"), col("late_minutes", "Late (min)", "number"),
        col("early_minutes", "Early (min)", "number"),
        col("overtime_hours", "OT (h)", "number", optional=ot_col),
        col("worked_hours", "Worked (h)", "number"),
        col("remote", "Remote", "bool", optional=features["has_remote"]),
    ]
    keys = ("present", "half_days", "absent", "on_leave", "incomplete", "late_days", "late_minutes",
            "early_minutes", "overtime_hours", "worked_hours")
    totals = {k: round(sum(r[k] for r in rows), 2) for k in keys}
    return build_report(
        key="attendance", title=f"Attendance summary {from_date:%d %b %Y} - {to_date:%d %b %Y}",
        filters=filters, columns=columns, rows=rows, totals=totals,
        chart_data=chart("bar", ["Present", "Half days", "Absent", "On leave"],
                         [{"name": "Days", "data": [totals["present"], totals["half_days"],
                                                    totals["absent"], totals["on_leave"]]}]),
    )
