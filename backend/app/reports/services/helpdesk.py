"""Helpdesk report: tickets raised in a period, or a summary per category."""
from django.db.models import Count, Q
from django.utils import timezone

from common.permissions import get_user_employee

from .common import (
    ReportError, build_report, chart, col, day_end_exclusive, day_start, days_between, dept_name, emp_name,
    parse_period,
)

STATUSES = ("OPEN", "IN_PROGRESS", "ON_HOLD", "RESOLVED", "CLOSED")
PRIORITIES = ("LOW", "MEDIUM", "HIGH", "URGENT")
REOPEN_TEXT = "from Resolved to"


def _hours(start, end):
    if not start or not end:
        return None
    return round((end - start).total_seconds() / 3600, 1)


def helpdesk_report(request, organization, data, features):
    from app.helpdesk.services import staff_queryset

    from_date, to_date = parse_period(data)
    view = str(data.get("view") or "tickets").lower()
    if view not in ("tickets", "summary"):
        raise ReportError("view must be tickets or summary.")
    status = str(data.get("status") or "").upper() or None
    if status and status not in STATUSES:
        raise ReportError(f"status must be one of {', '.join(STATUSES)}.")
    priority = str(data.get("priority") or "").upper() or None
    if priority and priority not in PRIORITIES:
        raise ReportError(f"priority must be one of {', '.join(PRIORITIES)}.")

    employee = get_user_employee(request.user, organization)
    scoped = staff_queryset(request, organization, employee)        # manage: all; handle: own department + assigned
    if data.get("category_id"):
        scoped = scoped.filter(category_id=data.get("category_id"))
    if priority:
        scoped = scoped.filter(priority=priority)
    if data.get("assigned_to_id"):
        scoped = scoped.filter(assigned_to_id=data.get("assigned_to_id"))
    if str(data.get("unassigned_only", "")).lower() in ("true", "1", "yes"):
        scoped = scoped.filter(assigned_to__isnull=True)
    start, end = day_start(from_date), day_end_exclusive(to_date)
    raised = scoped.filter(created_at__gte=start, created_at__lt=end)

    filters = {"from_date": str(from_date), "to_date": str(to_date), "view": view}
    for k in ("status", "priority", "category_id", "assigned_to_id", "unassigned_only", "search"):
        if data.get(k):
            filters[k] = data.get(k)
    now = timezone.now()

    if view == "summary":
        cats = {}
        for t in raised.select_related("category"):
            c = cats.setdefault(t.category_id, {"category": t.category.name, "raised": 0, "resolved": 0,
                                                "hours": []})
            c["raised"] += 1
            if t.resolved_at and start <= t.resolved_at < end:
                c["resolved"] += 1
                c["hours"].append(_hours(t.created_at, t.resolved_at))
        for row in scoped.exclude(status__in=("RESOLVED", "CLOSED")).values("category_id", "category__name") \
                .annotate(n=Count("id")):
            c = cats.setdefault(row["category_id"], {"category": row["category__name"], "raised": 0, "resolved": 0,
                                                     "hours": []})
            c["open_now"] = row["n"]
        oldest = {}
        for t in scoped.exclude(status__in=("RESOLVED", "CLOSED")).only("category_id", "created_at"):
            age = (now - t.created_at).days
            oldest[t.category_id] = max(oldest.get(t.category_id, 0), age)
        rows = []
        for cid, c in sorted(cats.items(), key=lambda kv: kv[1]["category"]):
            hours = [h for h in c["hours"] if h is not None]
            rows.append({"category": c["category"], "raised": c["raised"], "resolved": c["resolved"],
                         "open_now": c.get("open_now", 0),
                         "average_resolution_hours": round(sum(hours) / len(hours), 1) if hours else None,
                         "oldest_open_days": oldest.get(cid)})
        columns = [col("category", "Category"), col("raised", "Raised", "number"),
                   col("resolved", "Resolved in period", "number"), col("open_now", "Open now", "number"),
                   col("average_resolution_hours", "Avg resolution (h)", "number"),
                   col("oldest_open_days", "Oldest open (days)", "number")]
        return build_report(
            key="helpdesk", title=f"Helpdesk summary {from_date:%d %b %Y} - {to_date:%d %b %Y}",
            filters=filters, columns=columns, rows=rows,
            totals={k: sum(r[k] for r in rows) for k in ("raised", "resolved", "open_now")},
            chart_data=chart("bar", [r["category"] for r in rows], [
                {"name": "Raised", "data": [r["raised"] for r in rows]},
                {"name": "Resolved", "data": [r["resolved"] for r in rows]},
            ]),
        )

    tickets = raised
    if status:
        tickets = tickets.filter(status=status)
    search = (data.get("search") or "").strip()
    if search:
        tickets = tickets.filter(Q(ticket_code__icontains=search) | Q(subject__icontains=search)
                                 | Q(raised_by__first_name__icontains=search)
                                 | Q(raised_by__last_name__icontains=search))
    tickets = tickets.select_related("category", "raised_by", "raised_by__department_ref", "assigned_to") \
        .annotate(reopens=Count("comments", filter=Q(comments__is_system=True,
                                                    comments__message__contains=REOPEN_TEXT))) \
        .order_by("created_at")
    rows = [{
        "ticket_code": t.ticket_code,
        "raised_on": timezone.localtime(t.created_at).strftime("%Y-%m-%d %H:%M"),
        "raised_by": emp_name(t.raised_by), "department": dept_name(t.raised_by),
        "category": t.category.name, "subject": t.subject, "priority": t.get_priority_display(),
        "status": t.get_status_display(), "assigned_to": emp_name(t.assigned_to),
        "resolved_on": timezone.localtime(t.resolved_at).strftime("%Y-%m-%d %H:%M") if t.resolved_at else None,
        "resolution_hours": _hours(t.created_at, t.resolved_at),
        "open_days": None if t.status in ("RESOLVED", "CLOSED") else (now - t.created_at).days,
        "reopened": t.reopens > 0,
    } for t in tickets]
    columns = [
        col("ticket_code", "Ticket"), col("raised_on", "Raised on"), col("raised_by", "Raised by"),
        col("department", "Department", optional=features["has_departments"]),
        col("category", "Category"), col("subject", "Subject"), col("priority", "Priority"),
        col("status", "Status"), col("assigned_to", "Assigned to"),
        col("resolved_on", "Resolved on", optional="data"),
        col("resolution_hours", "Resolution (h)", "number", optional="data"),
        col("open_days", "Open (days)", "number", optional="data"),
        col("reopened", "Reopened", "bool", optional="data"),
    ]
    per_day_raised, per_day_resolved = {}, {}
    for t in raised.only("created_at", "resolved_at"):
        k = timezone.localtime(t.created_at).date()
        per_day_raised[k] = per_day_raised.get(k, 0) + 1
        if t.resolved_at:
            r = timezone.localtime(t.resolved_at).date()
            per_day_resolved[r] = per_day_resolved.get(r, 0) + 1
    days = list(days_between(from_date, to_date))
    resolved_hours = [r["resolution_hours"] for r in rows if r["resolution_hours"] is not None]
    return build_report(
        key="helpdesk", title=f"Tickets {from_date:%d %b %Y} - {to_date:%d %b %Y}",
        filters=filters, columns=columns, rows=rows,
        chart_data=chart("line", [d.strftime("%d %b") for d in days], [
            {"name": "Raised", "data": [per_day_raised.get(d, 0) for d in days]},
            {"name": "Resolved", "data": [per_day_resolved.get(d, 0) for d in days]},
        ]),
        extra={"summary": {
            "tickets": len(rows),
            "open": sum(1 for r in rows if r["open_days"] is not None),
            "average_resolution_hours": round(sum(resolved_hours) / len(resolved_hours), 1) if resolved_hours else None,
            "reopened": sum(1 for r in rows if r["reopened"]),
        }},
    )
