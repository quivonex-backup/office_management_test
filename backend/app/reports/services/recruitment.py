"""Recruitment report (applicants / funnel) + the visibility rule shared with the dashboard."""
from django.db.models import Count, Q

from common.permissions import get_user_employee, has_perm

from .common import ReportError, build_report, chart, col, emp_name, num, parse_period

# Same rule as the recruitment app: these codes see every applicant;
# applicant.view alone sees only the applicants assigned to / interviewed by them.
FULL_ACCESS_CODES = (
    "applicant.create", "applicant.update", "applicant.status_update",
    "verification.update", "onboarding.complete",
)


def visible_applicants(request, organization):
    from app.recruitment.models import Applicant

    qs = Applicant.objects.filter(organization=organization, is_active=True)
    if any(has_perm(request, organization, c) for c in FULL_ACCESS_CODES):
        return qs
    employee = get_user_employee(request.user, organization)
    if employee is None:
        return qs.none()
    return qs.filter(Q(assigned_to=employee) | Q(interviews__interviewer=employee)).distinct()


def recruitment_report(request, organization, data, features):
    from app.recruitment.models import Applicant

    from_date, to_date = parse_period(data)
    view = str(data.get("view") or "applicants").lower()
    if view not in ("applicants", "funnel"):
        raise ReportError("view must be applicants or funnel.")

    qs = visible_applicants(request, organization).filter(applied_on__gte=from_date, applied_on__lte=to_date)
    if data.get("designation_id"):
        qs = qs.filter(designation_id=data.get("designation_id"))
    if data.get("department_id") and features["has_departments"]:
        qs = qs.filter(department_id=data.get("department_id"))
    if data.get("assigned_to_id"):
        qs = qs.filter(assigned_to_id=data.get("assigned_to_id"))
    for key in ("stage", "status", "source"):
        if data.get(key):
            qs = qs.filter(**{key: str(data.get(key)).upper()})
    search = (data.get("search") or "").strip()
    if search:
        qs = qs.filter(Q(first_name__icontains=search) | Q(last_name__icontains=search)
                       | Q(applicant_code__icontains=search) | Q(email__icontains=search))

    filters = {"from_date": str(from_date), "to_date": str(to_date), "view": view}
    for k in ("stage", "status", "source", "designation_id", "department_id", "assigned_to_id", "search"):
        if data.get(k):
            filters[k] = data.get(k)

    stage_labels = dict(Applicant.STAGE_CHOICES)
    status_labels = dict(Applicant.STATUS_CHOICES)
    source_labels = dict(Applicant.SOURCE_CHOICES)

    applicants = list(
        qs.select_related("designation", "department", "assigned_to")
        .prefetch_related("interviews", "offers").order_by("-applied_on", "-id")
    )

    if view == "funnel":
        total = len(applicants)
        counts = {code: 0 for code, _l in Applicant.STAGE_CHOICES}
        reached = {code: 0 for code, _l in Applicant.STAGE_CHOICES}
        order = [code for code, _l in Applicant.STAGE_CHOICES if code != "CLOSED"]
        for a in applicants:
            counts[a.stage] += 1
            if a.stage in order:
                for code in order[: order.index(a.stage) + 1]:
                    reached[code] += 1
        rows = [{"stage": stage_labels[code], "current": counts[code], "reached": reached.get(code, 0),
                 "percent_of_applied": round(reached.get(code, 0) * 100 / total, 1) if total else 0.0}
                for code in order]
        rows.append({"stage": stage_labels["CLOSED"], "current": counts["CLOSED"], "reached": None,
                     "percent_of_applied": round(counts["CLOSED"] * 100 / total, 1) if total else 0.0})
        offers = [o for a in applicants for o in a.offers.all() if o.status != "SUPERSEDED"]
        hired = [a for a in applicants if a.converted_at]
        days_to_hire = [(a.converted_at.date() - a.applied_on).days for a in hired]
        columns = [col("stage", "Stage"), col("current", "Now in stage", "number"),
                   col("reached", "Reached stage", "number"), col("percent_of_applied", "% of applied", "number")]
        return build_report(
            key="recruitment", title=f"Hiring funnel {from_date:%d %b %Y} - {to_date:%d %b %Y}",
            filters=filters, columns=columns, rows=rows,
            chart_data=chart("bar", [r["stage"] for r in rows[:-1]],
                             [{"name": "Reached", "data": [r["reached"] for r in rows[:-1]]}]),
            extra={"summary": {
                "applied": total,
                "offers_sent": sum(1 for o in offers if o.status in ("SENT", "ACCEPTED", "DECLINED")),
                "offers_accepted": sum(1 for o in offers if o.status == "ACCEPTED"),
                "offers_declined": sum(1 for o in offers if o.status == "DECLINED"),
                "hired": len(hired),
                "average_days_to_hire": round(sum(days_to_hire) / len(days_to_hire), 1) if days_to_hire else None,
            }},
        )

    rows = []
    for a in applicants:
        interviews = sorted(a.interviews.all(), key=lambda i: (i.scheduled_at is None, i.scheduled_at or a.created_at))
        done = [i for i in interviews if i.result in ("PASSED", "FAILED", "ON_HOLD", "NO_SHOW")]
        offer = next((o for o in sorted(a.offers.all(), key=lambda o: -o.version) if o.status != "SUPERSEDED"), None)
        end = a.converted_at.date() if a.converted_at else to_date
        rows.append({
            "applicant_code": a.applicant_code,
            "name": " ".join(p for p in [a.first_name, a.last_name] if p),
            "applied_on": str(a.applied_on),
            "position": a.designation.name if a.designation else (a.position_title or None),
            "department": a.department.name if a.department else None,
            "source": source_labels.get(a.source, a.source),
            "assigned_to": emp_name(a.assigned_to),
            "stage": stage_labels.get(a.stage, a.stage),
            "status": status_labels.get(a.status, a.status),
            "interviews_done": len(done),
            "last_interview_result": done[-1].result if done else None,
            "offer_status": offer.status if offer else None,
            "offered_ctc": num(offer.annual_ctc) if offer else None,
            "joining_date": str(a.joining_date) if a.joining_date else None,
            "days_in_pipeline": max((end - a.applied_on).days, 0),
        })
    columns = [
        col("applicant_code", "Code"), col("name", "Name"), col("applied_on", "Applied on", "date"),
        col("position", "Position"), col("department", "Department", optional=features["has_departments"]),
        col("source", "Source"), col("assigned_to", "Assigned to", optional="data"),
        col("stage", "Stage"), col("status", "Status"),
        col("interviews_done", "Interviews done", "number"), col("last_interview_result", "Last result", optional="data"),
        col("offer_status", "Offer", optional="data"), col("offered_ctc", "Offered CTC", "money", optional="data"),
        col("joining_date", "Joining date", "date", optional="data"),
        col("days_in_pipeline", "Days in pipeline", "number"),
    ]
    weekly = {}
    for a in applicants:
        week = a.applied_on.isocalendar()
        key = f"{week[0]}-W{week[1]:02d}"
        weekly[key] = weekly.get(key, 0) + 1
    labels = sorted(weekly)
    return build_report(
        key="recruitment", title=f"Applicants {from_date:%d %b %Y} - {to_date:%d %b %Y}",
        filters=filters, columns=columns, rows=rows,
        chart_data=chart("line", labels, [{"name": "Applications", "data": [weekly[k] for k in labels]}]),
        extra={"summary": {"applicants": len(rows)}},
    )
