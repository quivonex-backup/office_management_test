"""Visitors report (batch 18): visit log for a period, or a summary by host / purpose / day."""
from django.db.models import Q
from django.utils import timezone

from .common import (
    ReportError, build_report, chart, col, day_end_exclusive, day_start, days_between, dept_name, emp_name,
    parse_period,
)

PURPOSES = ("MEETING", "INTERVIEW", "CLIENT", "VENDOR", "DELIVERY", "PERSONAL", "OTHER")


def _bool(value):
    return value is True or str(value).lower() in ("true", "1", "yes")


def _arrival(v):
    return v.check_in_at or v.created_at


def visitors_report(request, organization, data, features):
    from app.visitors.models import Visit

    from_date, to_date = parse_period(data)
    view = str(data.get("view") or "visits").lower()
    if view not in ("visits", "summary"):
        raise ReportError("view must be visits or summary.")
    group_by = str(data.get("group_by") or "host").lower()
    if view == "summary" and group_by not in ("host", "purpose", "day"):
        raise ReportError("group_by must be host, purpose or day.")
    purpose = str(data.get("purpose") or "").upper() or None
    if purpose and purpose not in PURPOSES:
        raise ReportError(f"purpose must be one of {', '.join(PURPOSES)}.")

    start, end = day_start(from_date), day_end_exclusive(to_date)
    visits = Visit.objects.filter(organization=organization, is_active=True).filter(
        Q(check_in_at__gte=start, check_in_at__lt=end)
        | Q(check_in_at__isnull=True, created_at__gte=start, created_at__lt=end)
    )
    if purpose:
        visits = visits.filter(purpose=purpose)
    if data.get("host_id"):
        visits = visits.filter(host_id=data.get("host_id"))
    if data.get("branch_id") and features["has_branches"]:
        visits = visits.filter(branch_id=data.get("branch_id"))
    if _bool(data.get("still_inside")):
        visits = visits.filter(check_in_at__isnull=False, check_out_at__isnull=True)
    search = (data.get("search") or "").strip()
    if search:
        visits = visits.filter(Q(visitor_name__icontains=search) | Q(visitor_mobile__icontains=search)
                               | Q(visitor_company__icontains=search) | Q(visit_code__icontains=search))
    visits = list(visits.select_related("host", "host__department_ref", "branch"))
    visits.sort(key=_arrival)

    filters = {"from_date": str(from_date), "to_date": str(to_date), "view": view}
    if view == "summary":
        filters["group_by"] = group_by
    for k in ("purpose", "host_id", "branch_id", "still_inside", "search"):
        if data.get(k) not in (None, ""):
            filters[k] = data.get(k)

    def minutes(v):
        if v.check_in_at and v.check_out_at and v.check_out_at > v.check_in_at:
            return int((v.check_out_at - v.check_in_at).total_seconds() // 60)
        return None

    labels = dict(Visit.PURPOSE_CHOICES)

    if view == "summary":
        groups = {}
        for v in visits:
            if group_by == "host":
                key = v.host_id or 0
                name = emp_name(v.host) if v.host else "No host"
                extra = {"department": dept_name(v.host) if v.host else None}
            elif group_by == "purpose":
                key, name, extra = v.purpose, labels.get(v.purpose, v.purpose), {}
            else:
                d = timezone.localtime(_arrival(v)).date()
                key, name, extra = d, str(d), {}
            g = groups.setdefault(key, {"group": name, **extra, "visits": 0, "visitors": 0, "mins": []})
            g["visits"] += 1
            g["visitors"] += v.visitor_count or 1
            m = minutes(v)
            if m is not None:
                g["mins"].append(m)
        if group_by == "day":
            for d in days_between(from_date, to_date):
                groups.setdefault(d, {"group": str(d), "visits": 0, "visitors": 0, "mins": []})
            ordered = [groups[k] for k in sorted(groups)]
        else:
            ordered = sorted(groups.values(), key=lambda g: (-g["visits"], g["group"]))
        rows = [{**{k: v for k, v in g.items() if k != "mins"},
                 "average_minutes": round(sum(g["mins"]) / len(g["mins"])) if g["mins"] else None}
                for g in ordered]
        title_by = {"host": "host", "purpose": "purpose", "day": "day"}[group_by]
        columns = [col("group", {"host": "Host", "purpose": "Purpose", "day": "Date"}[group_by]),
                   col("department", "Department", optional=group_by == "host" and features["has_departments"]),
                   col("visits", "Visits", "number"), col("visitors", "Visitors", "number"),
                   col("average_minutes", "Avg stay (min)", "number", optional="data")]
        return build_report(
            key="visitors", title=f"Visitors by {title_by} {from_date:%d %b %Y} - {to_date:%d %b %Y}",
            filters=filters, columns=columns, rows=rows,
            totals={"visits": sum(r["visits"] for r in rows), "visitors": sum(r["visitors"] for r in rows)},
            chart_data=chart("line" if group_by == "day" else "bar", [r["group"] for r in rows],
                             [{"name": "Visits", "data": [r["visits"] for r in rows]}]),
        )

    def t(value):
        return timezone.localtime(value).strftime("%H:%M") if value else None

    rows = []
    for v in visits:
        arrival = timezone.localtime(_arrival(v))
        rows.append({
            "visit_code": v.visit_code, "date": str(arrival.date()),
            "check_in": t(v.check_in_at), "check_out": t(v.check_out_at), "minutes": minutes(v),
            "visitor_name": v.visitor_name, "visitor_mobile": v.visitor_mobile, "visitor_company": v.visitor_company,
            "visitor_count": v.visitor_count, "purpose": labels.get(v.purpose, v.purpose),
            "host": emp_name(v.host), "host_department": dept_name(v.host) if v.host else None,
            "branch": v.branch.name if v.branch_id else None, "badge_number": v.badge_number,
            "vehicle_number": v.vehicle_number,
            "still_inside": bool(v.check_in_at and not v.check_out_at),
        })
    columns = [
        col("visit_code", "Visit"), col("date", "Date", "date"), col("check_in", "In", "time"),
        col("check_out", "Out", "time", optional="data"), col("minutes", "Stay (min)", "number", optional="data"),
        col("visitor_name", "Visitor"), col("visitor_mobile", "Mobile"),
        col("visitor_company", "Company", optional="data"), col("visitor_count", "People", "number"),
        col("purpose", "Purpose"), col("host", "Host", optional="data"),
        col("host_department", "Host department", optional=features["has_departments"]),
        col("branch", "Branch", optional=features["has_branches"]),
        col("badge_number", "Badge", optional="data"), col("vehicle_number", "Vehicle", optional="data"),
        col("still_inside", "Still inside", "bool", optional="data"),
    ]
    per_day = {}
    for r in rows:
        per_day[r["date"]] = per_day.get(r["date"], 0) + 1
    days = list(days_between(from_date, to_date))
    stays = [r["minutes"] for r in rows if r["minutes"] is not None]
    return build_report(
        key="visitors", title=f"Visitor log {from_date:%d %b %Y} - {to_date:%d %b %Y}",
        filters=filters, columns=columns, rows=rows,
        totals={"visitor_count": sum(r["visitor_count"] or 0 for r in rows)},
        chart_data=chart("line", [d.strftime("%d %b") for d in days],
                         [{"name": "Visits", "data": [per_day.get(str(d), 0) for d in days]}]),
        extra={"summary": {"visits": len(rows), "visitors": sum(r["visitor_count"] or 0 for r in rows),
                           "still_inside": sum(1 for r in rows if r["still_inside"]),
                           "average_minutes": round(sum(stays) / len(stays)) if stays else None}},
    )
