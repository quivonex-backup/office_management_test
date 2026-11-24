"""Payroll report: salary register for one payroll run (columns follow the payroll setup)."""
from decimal import Decimal

from .common import (
    ZERO, ReportError, apply_employee_filters, branch_name, build_report, chart, col, dept_name, emp_name,
    month_bounds, num, parse_day,
)

PAYMENT_STATUSES = ("UNPAID", "PARTIALLY_PAID", "PAID")


def _pick_run(organization, data):
    from app.payroll.models import PayrollRun

    runs = PayrollRun.objects.filter(organization=organization)
    if data.get("payroll_run_id"):
        run = runs.filter(id=data.get("payroll_run_id")).first()
        if run is None:
            raise ReportError("Payroll run not found.", http_status=404)
        return run
    if data.get("month"):
        raw = str(data.get("month")).strip()
        day = parse_day(f"{raw}-01" if len(raw) == 7 else raw, "month")
        first, last = month_bounds(day)
        run = runs.filter(period_end__gte=first, period_end__lte=last).order_by("-period_end", "-id").first()
        if run is None:
            raise ReportError(f"No payroll run ends in {first:%B %Y}.", http_status=404)
        return run
    run = runs.order_by("-period_end", "-id").first()
    if run is None:
        raise ReportError("No payroll runs yet.", http_status=404)
    return run


def payroll_report(request, organization, data, features):
    from app.payroll.models import PayrollRun

    run = _pick_run(organization, data)
    status = str(data.get("payment_status") or "").upper() or None
    if status and status not in PAYMENT_STATUSES:
        raise ReportError(f"payment_status must be one of {', '.join(PAYMENT_STATUSES)}.")

    records = run.records.filter(generation_status="GENERATED")
    if status:
        records = records.filter(payment_status=status)
    if str(data.get("requires_review", "")).lower() in ("true", "1", "yes"):
        records = records.filter(requires_review=True)
    records = apply_employee_filters(records, data, features) \
        .select_related("employee", "employee__department_ref", "employee__branch") \
        .prefetch_related("line_items").order_by("employee__employee_code")

    rows = []
    for r in records:
        items = {}
        for li in r.line_items.all():
            items[li.component_code] = items.get(li.component_code, ZERO) + li.amount
        paid_days = (r.present_days + r.half_days * Decimal("0.5") + r.paid_leave_days
                     + r.holiday_days + r.weekly_off_days)
        employer = r.pf_employer + r.eps + r.edli + r.esi_employer + r.lwf_employer
        rows.append({
            "employee_code": r.employee.employee_code, "name": emp_name(r.employee),
            "department": dept_name(r.employee), "branch": branch_name(r.employee),
            "monthly_salary": num(r.monthly_salary),
            "paid_days": num(paid_days), "absent_days": num(r.absent_days), "half_days": num(r.half_days),
            "unpaid_leave_days": num(r.unpaid_leave_days),
            "late_minutes": r.late_minutes, "overtime_hours": num(r.overtime_hours),
            "overtime_amount": num(items.get("OT", ZERO)),
            "gross": num(r.gross_earnings),
            "lop": num(items.get("LOP", ZERO)),
            "late_deduction": num(items.get("LATE", ZERO)),
            "pf": num(r.pf_employee), "vpf": num(r.vpf_employee), "esi": num(r.esi_employee),
            "pt": num(r.pt), "lwf": num(r.lwf_employee), "tds": num(r.tds),
            "other_deductions": num(r.other_deductions),
            "total_deductions": num(r.total_deductions), "net": num(r.net),
            "pf_employer": num(r.pf_employer + r.eps + r.edli), "esi_employer": num(r.esi_employer),
            "lwf_employer": num(r.lwf_employer),
            "employer_cost": num(r.gross_earnings + employer) if employer else None,
            "payment_status": r.get_payment_status_display(), "paid_amount": num(r.paid_amount),
            "requires_review": r.requires_review,
        })

    f = features
    columns = [
        col("employee_code", "Code"), col("name", "Employee"),
        col("department", "Department", optional=f["has_departments"]),
        col("branch", "Branch", optional=f["has_branches"]),
        col("monthly_salary", "Monthly salary", "money"),
        col("paid_days", "Paid days", "number"), col("absent_days", "Absent", "number"),
        col("half_days", "Half days", "number", optional="data"),
        col("unpaid_leave_days", "Unpaid leave", "number", optional="data"),
        col("late_minutes", "Late (min)", "number", optional=f["late_deduction_enabled"]),
        col("overtime_hours", "OT (h)", "number", optional=f["overtime_enabled"]),
        col("overtime_amount", "OT amount", "money", optional=f["overtime_enabled"]),
        col("gross", "Gross", "money"),
        col("lop", "Loss of pay", "money", optional="data"),
        col("late_deduction", "Late deduction", "money", optional=f["late_deduction_enabled"]),
        col("pf", "PF", "money", optional=f["pf"]), col("vpf", "VPF", "money", optional=f["vpf"]),
        col("esi", "ESI", "money", optional=f["esi"]), col("pt", "PT", "money", optional=f["pt"]),
        col("lwf", "LWF", "money", optional=f["lwf"]), col("tds", "TDS", "money", optional="data"),
        col("other_deductions", "Other deductions", "money", optional="data"),
        col("total_deductions", "Total deductions", "money"), col("net", "Net pay", "money"),
        col("pf_employer", "PF employer (incl. EPS, EDLI)", "money", optional=f["pf"]),
        col("esi_employer", "ESI employer", "money", optional=f["esi"]),
        col("lwf_employer", "LWF employer", "money", optional=f["lwf"]),
        col("employer_cost", "Employer cost", "money", optional=bool(f["pf"] or f["esi"] or f["lwf"])),
        col("payment_status", "Payment"), col("paid_amount", "Paid", "money"),
        col("requires_review", "Needs review", "bool", optional="data"),
    ]
    money_keys = ("monthly_salary", "overtime_amount", "gross", "lop", "late_deduction", "pf", "vpf", "esi", "pt",
                  "lwf", "tds", "other_deductions", "total_deductions", "net", "pf_employer", "esi_employer",
                  "lwf_employer", "employer_cost", "paid_amount", "late_minutes", "overtime_hours")
    totals = {k: round(sum((row[k] or 0) for row in rows), 2) for k in money_keys}

    recent = list(PayrollRun.objects.filter(organization=organization, period_end__lte=run.period_end)
                  .order_by("-period_end")[:6])[::-1]
    filters = {"payroll_run_id": run.id, "period_start": str(run.period_start), "period_end": str(run.period_end),
               "run_status": run.status}
    for k in ("payment_status", "employee_id", "department_id", "branch_id", "designation_id", "search"):
        if data.get(k):
            filters[k] = data.get(k)
    runs = [{"id": x.id, "period_start": str(x.period_start), "period_end": str(x.period_end),
             "status": x.status}
            for x in PayrollRun.objects.filter(organization=organization).order_by("-period_end")[:24]]
    return build_report(
        key="payroll", title=f"Salary register {run.period_start:%d %b %Y} - {run.period_end:%d %b %Y}",
        filters=filters, columns=columns, rows=rows, totals=totals,
        chart_data=chart("bar", [x.period_end.strftime("%b %Y") for x in recent], [
            {"name": "Gross", "data": [num(x.total_gross) for x in recent]},
            {"name": "Deductions", "data": [num(x.total_deductions) for x in recent]},
            {"name": "Net", "data": [num(x.total_net) for x in recent]},
        ]),
        extra={"runs": runs, "payslip_mode": features["payslip_mode"]},
    )
