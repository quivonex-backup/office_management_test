"""Projects report: one row per project (task progress) or per assignee."""
from django.db.models import Count, Q
from django.utils import timezone

from .common import ReportError, build_report, chart, col, day_end_exclusive, day_start, emp_name, num, parse_period

PROJECT_STATUSES = ("new", "in_progress", "testing", "completed", "on_hold", "cancelled")


def projects_report(request, organization, data, features):
    from app.projects.models import Project, ProjectTeamAllocation, Task

    from_date, to_date = parse_period(data)
    today = timezone.localdate()
    view = str(data.get("view") or "projects").lower()
    if view not in ("projects", "assignees"):
        raise ReportError("view must be projects or assignees.")
    project_status = str(data.get("project_status") or "").lower() or None
    if project_status and project_status not in PROJECT_STATUSES:
        raise ReportError(f"project_status must be one of {', '.join(PROJECT_STATUSES)}.")
    overdue_only = str(data.get("overdue_only", "")).lower() in ("true", "1", "yes")

    projects = Project.objects.filter(organization=organization, is_active=True)
    if project_status:
        projects = projects.filter(status=project_status)
    if data.get("project_id"):
        projects = projects.filter(id=data.get("project_id"))
    if data.get("client_id"):
        projects = projects.filter(client_id=data.get("client_id"))
    search = (data.get("search") or "").strip()

    tasks = Task.objects.filter(organization=organization, is_active=True, project__in=projects)
    if data.get("assignee_id"):
        tasks = tasks.filter(assigned_to_id=data.get("assignee_id"))
    open_q = ~Q(status="DONE")
    overdue_q = open_q & Q(due_date__lt=today)
    done_in_period = Q(status="DONE", completed_at__gte=day_start(from_date),
                       completed_at__lt=day_end_exclusive(to_date))

    filters = {"from_date": str(from_date), "to_date": str(to_date), "view": view}
    for k in ("project_status", "project_id", "client_id", "assignee_id", "overdue_only", "search"):
        if data.get(k):
            filters[k] = data.get(k)

    if view == "assignees":
        agg = tasks.values("assigned_to").annotate(
            total=Count("id"), open=Count("id", filter=open_q), overdue=Count("id", filter=overdue_q),
            done_in_period=Count("id", filter=done_in_period),
            projects=Count("project", distinct=True),
        )
        from app.employees.models import Employee

        people = {e.id: e for e in Employee.objects.filter(id__in=[a["assigned_to"] for a in agg if a["assigned_to"]])}
        rows = []
        for a in agg:
            emp = people.get(a["assigned_to"])
            name = emp_name(emp) if emp else "Unassigned"
            if search and search.lower() not in name.lower():
                continue
            if overdue_only and not a["overdue"]:
                continue
            rows.append({"employee_code": emp.employee_code if emp else None, "name": name,
                         "projects": a["projects"], "total_tasks": a["total"], "open_tasks": a["open"],
                         "overdue_tasks": a["overdue"], "done_in_period": a["done_in_period"]})
        rows.sort(key=lambda r: (-r["overdue_tasks"], -r["open_tasks"], r["name"]))
        columns = [col("employee_code", "Code"), col("name", "Assignee"), col("projects", "Projects", "number"),
                   col("total_tasks", "Tasks", "number"), col("open_tasks", "Open", "number"),
                   col("overdue_tasks", "Overdue", "number"), col("done_in_period", "Done in period", "number")]
        keys = ("total_tasks", "open_tasks", "overdue_tasks", "done_in_period")
        return build_report(
            key="projects", title=f"Tasks by assignee {from_date:%d %b %Y} - {to_date:%d %b %Y}",
            filters=filters, columns=columns, rows=rows, totals={k: sum(r[k] for r in rows) for k in keys},
            chart_data=chart("bar", [r["name"] for r in rows[:15]], [
                {"name": "Open", "data": [r["open_tasks"] for r in rows[:15]]},
                {"name": "Overdue", "data": [r["overdue_tasks"] for r in rows[:15]]},
            ]),
        )

    counts = {r["project"]: r for r in tasks.values("project").annotate(
        total=Count("id"), done=Count("id", filter=Q(status="DONE")), open=Count("id", filter=open_q),
        overdue=Count("id", filter=overdue_q), done_in_period=Count("id", filter=done_in_period))}
    heads = {}
    for al in ProjectTeamAllocation.objects.filter(project__in=projects, is_active=True, is_project_head=True) \
            .select_related("employee"):
        heads.setdefault(al.project_id, []).append(emp_name(al.employee))
    rows = []
    for p in projects.select_related("client").order_by("project_name"):
        c = counts.get(p.id, {})
        if search and search.lower() not in (p.project_name + " " + (p.client.client_name if p.client else "")).lower():
            continue
        if overdue_only and not c.get("overdue"):
            continue
        total = c.get("total", 0)
        rows.append({
            "project_code": p.project_code, "project": p.project_name,
            "client": p.client.client_name if p.client else None,
            "status": p.get_status_display(), "priority": p.get_priority_display(),
            "heads": ", ".join(heads.get(p.id, [])) or None,
            "start_date": str(p.start_date) if p.start_date else None,
            "deadline": str(p.deadline) if p.deadline else None,
            "late": bool(p.deadline and p.deadline < today and p.status not in ("completed", "cancelled")),
            "total_tasks": total, "done_tasks": c.get("done", 0), "open_tasks": c.get("open", 0),
            "overdue_tasks": c.get("overdue", 0), "done_in_period": c.get("done_in_period", 0),
            "percent_complete": round(c.get("done", 0) * 100 / total, 1) if total else 0.0,
            "total_cost": num(p.total_cost),
        })
    columns = [
        col("project_code", "Code"), col("project", "Project"), col("client", "Client"), col("status", "Status"),
        col("priority", "Priority"), col("heads", "Project head", optional="data"),
        col("start_date", "Start", "date", optional="data"), col("deadline", "Deadline", "date", optional="data"),
        col("late", "Past deadline", "bool", optional="data"),
        col("total_tasks", "Tasks", "number"), col("done_tasks", "Done", "number"),
        col("open_tasks", "Open", "number"), col("overdue_tasks", "Overdue", "number"),
        col("done_in_period", "Done in period", "number"), col("percent_complete", "% complete", "number"),
        col("total_cost", "Project value", "money"),
    ]
    keys = ("total_tasks", "done_tasks", "open_tasks", "overdue_tasks", "done_in_period", "total_cost")
    by_status = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    return build_report(
        key="projects", title=f"Projects {from_date:%d %b %Y} - {to_date:%d %b %Y}",
        filters=filters, columns=columns, rows=rows,
        totals={k: round(sum(r[k] or 0 for r in rows), 2) for k in keys},
        chart_data=chart("bar", [r["project"] for r in rows[:15]], [
            {"name": "Done", "data": [r["done_tasks"] for r in rows[:15]]},
            {"name": "Open", "data": [r["open_tasks"] for r in rows[:15]]},
        ]),
        extra={"summary": {"projects": len(rows), "by_status": by_status}},
    )
