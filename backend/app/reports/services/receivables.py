"""Receivables report: project payment rows (advance / installments) due in a period + collections."""

from django.db.models import Max, Q, Sum
from django.utils import timezone

from .common import ZERO, ReportError, build_report, chart, col, num, parse_period

STATUSES = ("PENDING", "PARTIALLY_PAID", "PAID", "OVERDUE")
BUCKETS = (("0-30", 0, 30), ("31-60", 31, 60), ("61-90", 61, 90), ("90+", 91, None))


def receivables_report(request, organization, data, features):
    from app.payments.models import ProjectPayment, ProjectPaymentTransaction

    from_date, to_date = parse_period(data)
    today = timezone.localdate()
    status = str(data.get("status") or "").upper() or None
    if status and status not in STATUSES:
        raise ReportError(f"status must be one of {', '.join(STATUSES)}.")
    overdue_only = str(data.get("overdue_only", "")).lower() in ("true", "1", "yes")
    include_undated = str(data.get("include_undated", "")).lower() in ("true", "1", "yes")

    qs = ProjectPayment.objects.filter(project__organization=organization, project__is_active=True) \
        .exclude(status="CANCELLED")
    if overdue_only:
        qs = qs.filter(outstanding_amount__gt=0, due_date__lt=today)
    else:
        period = Q(due_date__gte=from_date, due_date__lte=to_date)
        qs = qs.filter(period | Q(due_date__isnull=True)) if include_undated else qs.filter(period)
    if status:
        qs = qs.filter(status=status)
    if data.get("client_id"):
        qs = qs.filter(project__client_id=data.get("client_id"))
    if data.get("project_id"):
        qs = qs.filter(project_id=data.get("project_id"))
    if data.get("payment_type"):
        qs = qs.filter(payment_type=str(data.get("payment_type")).upper())
    search = (data.get("search") or "").strip()
    if search:
        qs = qs.filter(Q(project__project_name__icontains=search) | Q(project__client__client_name__icontains=search)
                       | Q(title__icontains=search))
    qs = qs.select_related("project", "project__client").annotate(
        last_paid=Max("transactions__transaction_date", filter=Q(transactions__status="SUCCESS")),
    ).order_by("due_date", "project__project_name", "installment_number")

    rows = []
    for p in qs:
        overdue_days = (today - p.due_date).days if (p.due_date and p.outstanding_amount > 0 and p.due_date < today) else 0
        rows.append({
            "client": p.project.client.client_name if p.project.client else None,
            "project": p.project.project_name, "project_code": p.project.project_code,
            "payment_type": p.get_payment_type_display(),
            "installment": p.installment_number, "title": p.title,
            "due_date": str(p.due_date) if p.due_date else None,
            "amount": num(p.amount), "paid": num(p.paid_amount), "outstanding": num(p.outstanding_amount),
            "status": p.get_status_display(), "days_overdue": overdue_days,
            "last_payment_date": str(p.last_paid) if p.last_paid else None,
        })
    columns = [
        col("client", "Client"), col("project", "Project"), col("project_code", "Project code"),
        col("payment_type", "Type"), col("installment", "Installment", "number", optional="data"),
        col("title", "Title", optional="data"), col("due_date", "Due date", "date"),
        col("amount", "Amount", "money"), col("paid", "Received", "money"),
        col("outstanding", "Outstanding", "money"), col("status", "Status"),
        col("days_overdue", "Days overdue", "number"),
        col("last_payment_date", "Last payment", "date", optional="data"),
    ]

    # Ageing of everything overdue today (same client / project filters, ignores the period)
    aged = ProjectPayment.objects.filter(project__organization=organization, project__is_active=True,
                                         outstanding_amount__gt=0, due_date__lt=today).exclude(status="CANCELLED")
    if data.get("client_id"):
        aged = aged.filter(project__client_id=data.get("client_id"))
    if data.get("project_id"):
        aged = aged.filter(project_id=data.get("project_id"))
    ageing = {label: ZERO for label, _a, _b in BUCKETS}
    for p in aged.only("due_date", "outstanding_amount"):
        days = (today - p.due_date).days
        for label, low, high in BUCKETS:
            if days >= low and (high is None or days <= high):
                ageing[label] += p.outstanding_amount
                break

    tx = ProjectPaymentTransaction.objects.filter(payment__project__organization=organization, status="SUCCESS",
                                                  transaction_date__gte=from_date, transaction_date__lte=to_date)
    if data.get("client_id"):
        tx = tx.filter(payment__project__client_id=data.get("client_id"))
    if data.get("project_id"):
        tx = tx.filter(payment__project_id=data.get("project_id"))
    collected = tx.aggregate(v=Sum("amount"))["v"] or ZERO

    filters = {"from_date": str(from_date), "to_date": str(to_date)}
    for k in ("status", "client_id", "project_id", "payment_type", "overdue_only", "include_undated", "search"):
        if data.get(k):
            filters[k] = data.get(k)
    totals = {k: round(sum(r[k] or 0 for r in rows), 2) for k in ("amount", "paid", "outstanding")}
    title = "Overdue receivables" if overdue_only else f"Receivables due {from_date:%d %b %Y} - {to_date:%d %b %Y}"
    return build_report(
        key="receivables", title=title, filters=filters, columns=columns, rows=rows, totals=totals,
        chart_data=chart("bar", list(ageing.keys()),
                         [{"name": "Overdue outstanding", "data": [num(v) for v in ageing.values()]}]),
        extra={"summary": {
            "collected_in_period": num(collected),
            "overdue_total": num(sum(ageing.values(), ZERO)),
            "ageing_days": {k: num(v) for k, v in ageing.items()},
        }},
    )
