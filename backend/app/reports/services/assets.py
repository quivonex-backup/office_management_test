"""Assets report (batch 18): asset register, holders, issue / return history."""
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from .common import ReportError, build_report, chart, col, dept_name, emp_name, num, parse_period

STATUSES = ("AVAILABLE", "ASSIGNED", "IN_REPAIR", "RETIRED", "LOST")


def assets_report(request, organization, data, features):
    from app.assets.models import Asset, AssetAssignment

    view = str(data.get("view") or "register").lower()
    if view not in ("register", "holders", "history"):
        raise ReportError("view must be register, holders or history.")
    status = str(data.get("status") or "").upper() or None
    if status and status not in STATUSES:
        raise ReportError(f"status must be one of {', '.join(STATUSES)}.")
    today = timezone.localdate()

    assets = Asset.objects.filter(organization=organization, is_active=True)
    if data.get("category_id"):
        assets = assets.filter(category_id=data.get("category_id"))
    if data.get("branch_id") and features["has_branches"]:
        assets = assets.filter(branch_id=data.get("branch_id"))
    search = (data.get("search") or "").strip()

    filters = {"view": view}
    for k in ("status", "category_id", "branch_id", "employee_id", "warranty_expiring_days", "search"):
        if data.get(k) not in (None, ""):
            filters[k] = data.get(k)

    # -------------------------------------------------- history (period)
    if view == "history":
        from_date, to_date = parse_period(data)
        filters.update({"from_date": str(from_date), "to_date": str(to_date)})
        qs = (
            AssetAssignment.objects.filter(asset__in=assets)
            .filter(Q(assigned_on__range=(from_date, to_date)) | Q(returned_on__range=(from_date, to_date)))
            .select_related("asset", "asset__category", "employee", "employee__department_ref")
            .order_by("assigned_on", "id")
        )
        if data.get("employee_id"):
            qs = qs.filter(employee_id=data.get("employee_id"))
        if search:
            qs = qs.filter(Q(asset__asset_code__icontains=search) | Q(asset__name__icontains=search)
                           | Q(employee__first_name__icontains=search) | Q(employee__last_name__icontains=search)
                           | Q(employee__employee_code__icontains=search))
        rows = []
        for a in qs:
            end = a.returned_on or today
            rows.append({
                "asset_code": a.asset.asset_code, "asset": a.asset.name, "category": a.asset.category.name,
                "employee_code": a.employee.employee_code, "employee": emp_name(a.employee),
                "department": dept_name(a.employee),
                "assigned_on": str(a.assigned_on), "condition_on_issue": a.get_condition_on_issue_display()
                if a.condition_on_issue else None,
                "returned_on": str(a.returned_on) if a.returned_on else None,
                "condition_on_return": a.get_condition_on_return_display() if a.condition_on_return else None,
                "days_held": (end - a.assigned_on).days,
                "issued_in_period": from_date <= a.assigned_on <= to_date,
                "returned_in_period": bool(a.returned_on and from_date <= a.returned_on <= to_date),
            })
        columns = [
            col("asset_code", "Asset"), col("asset", "Name"), col("category", "Category"),
            col("employee_code", "Emp code"), col("employee", "Employee"),
            col("department", "Department", optional=features["has_departments"]),
            col("assigned_on", "Issued on", "date"), col("condition_on_issue", "Condition (issue)", optional="data"),
            col("returned_on", "Returned on", "date", optional="data"),
            col("condition_on_return", "Condition (return)", optional="data"),
            col("days_held", "Days held", "number"),
        ]
        issued = sum(1 for r in rows if r["issued_in_period"])
        returned = sum(1 for r in rows if r["returned_in_period"])
        return build_report(
            key="assets", title=f"Asset issue / return {from_date:%d %b %Y} - {to_date:%d %b %Y}",
            filters=filters, columns=columns, rows=rows,
            chart_data=chart("bar", ["Issued", "Returned"], [{"name": "Assignments", "data": [issued, returned]}]),
            extra={"summary": {"assignments": len(rows), "issued": issued, "returned": returned,
                               "still_held": sum(1 for r in rows if not r["returned_on"])}},
        )

    # -------------------------------------------------- holders (now)
    if view == "holders":
        held = assets.filter(status="ASSIGNED", current_holder__isnull=False) \
            .select_related("current_holder", "current_holder__department_ref", "category")
        if data.get("employee_id"):
            held = held.filter(current_holder_id=data.get("employee_id"))
        if search:
            held = held.filter(Q(current_holder__first_name__icontains=search)
                               | Q(current_holder__last_name__icontains=search)
                               | Q(current_holder__employee_code__icontains=search))
        people = {}
        for a in held.order_by("current_holder__employee_code", "asset_code"):
            e = a.current_holder
            p = people.setdefault(e.id, {"employee_code": e.employee_code, "employee": emp_name(e),
                                         "department": dept_name(e), "assets_held": 0, "value": 0.0,
                                         "assets": []})
            p["assets_held"] += 1
            p["value"] += float(a.purchase_cost or 0)
            p["assets"].append(f"{a.asset_code} {a.name}")
        rows = []
        for p in people.values():
            p["value"] = round(p["value"], 2)
            p["assets"] = ", ".join(p["assets"])
            rows.append(p)
        columns = [col("employee_code", "Emp code"), col("employee", "Employee"),
                   col("department", "Department", optional=features["has_departments"]),
                   col("assets_held", "Assets held", "number"), col("value", "Purchase value", "money",
                                                                     optional="data"),
                   col("assets", "Assets")]
        return build_report(
            key="assets", title=f"Assets held by employees ({today:%d %b %Y})", filters=filters,
            columns=columns, rows=rows,
            totals={"assets_held": sum(r["assets_held"] for r in rows),
                    "value": round(sum(r["value"] for r in rows), 2)},
            extra={"summary": {"employees": len(rows), "assets_held": sum(r["assets_held"] for r in rows)}},
        )

    # -------------------------------------------------- register (now)
    reg = assets
    if status:
        reg = reg.filter(status=status)
    if data.get("employee_id"):
        reg = reg.filter(current_holder_id=data.get("employee_id"))
    if data.get("warranty_expiring_days") not in (None, ""):
        try:
            days = int(data.get("warranty_expiring_days"))
            if days < 0:
                raise ValueError
        except (TypeError, ValueError):
            raise ReportError("warranty_expiring_days must be a whole number >= 0.")
        reg = reg.filter(warranty_until__gte=today, warranty_until__lte=today + timedelta(days=days))
    if search:
        reg = reg.filter(Q(asset_code__icontains=search) | Q(name__icontains=search)
                         | Q(serial_number__icontains=search) | Q(brand__icontains=search))
    reg = reg.select_related("category", "branch", "current_holder").order_by("category__name", "asset_code")
    open_since = dict(
        AssetAssignment.objects.filter(asset__in=reg, returned_on__isnull=True).values_list("asset_id", "assigned_on")
    )
    rows = [{
        "asset_code": a.asset_code, "name": a.name, "category": a.category.name, "brand": a.brand,
        "model_number": a.model_number, "serial_number": a.serial_number,
        "branch": a.branch.name if a.branch_id else None, "status": a.get_status_display(),
        "holder": emp_name(a.current_holder), "holder_code": a.current_holder.employee_code if a.current_holder else None,
        "assigned_on": str(open_since[a.id]) if a.id in open_since else None,
        "purchase_date": str(a.purchase_date) if a.purchase_date else None,
        "purchase_cost": num(a.purchase_cost),
        "warranty_until": str(a.warranty_until) if a.warranty_until else None,
        "warranty_expired": bool(a.warranty_until and a.warranty_until < today),
        "_status": a.status,
    } for a in reg]
    columns = [
        col("asset_code", "Asset"), col("name", "Name"), col("category", "Category"),
        col("brand", "Brand", optional="data"), col("model_number", "Model", optional="data"),
        col("serial_number", "Serial no.", optional="data"),
        col("branch", "Branch", optional=features["has_branches"]), col("status", "Status"),
        col("holder_code", "Holder code", optional="data"), col("holder", "Holder", optional="data"),
        col("assigned_on", "Assigned on", "date", optional="data"),
        col("purchase_date", "Purchase date", "date", optional="data"),
        col("purchase_cost", "Purchase cost", "money", optional="data"),
        col("warranty_until", "Warranty until", "date", optional="data"),
        col("warranty_expired", "Warranty expired", "bool", optional="data"),
    ]
    by_status = {s: sum(1 for r in rows if r["_status"] == s) for s in STATUSES}
    labels = dict(Asset.STATUS_CHOICES)
    return build_report(
        key="assets", title=f"Asset register ({today:%d %b %Y})", filters=filters, columns=columns, rows=rows,
        totals={"purchase_cost": round(sum(float(r["purchase_cost"] or 0) for r in rows), 2)},
        chart_data=chart("bar", [labels[s] for s in STATUSES], [{"name": "Assets",
                                                                  "data": [by_status[s] for s in STATUSES]}]),
        extra={"summary": {"assets": len(rows), **{s.lower(): by_status[s] for s in STATUSES},
                           "warranty_expired": sum(1 for r in rows if r["warranty_expired"])}},
    )
