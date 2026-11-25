"""
Payroll calculator (what-if). Read-only: nothing is saved.

Self-contained: this one file is the whole feature. It reuses the existing
statutory and component helpers from .computation (PF / ESI / PT / LWF and
structure resolution) so rates, ceilings and slabs are never duplicated, and
it only READS settings and statutory rows. Nothing is written to the database.

The arithmetic after the day counts (base days, loss of pay, overtime, line
items) is a copy of the tail of compute_payslip_data, kept here so no existing
service file has to change. If that tail changes later, change _build_payslip
the same way.
"""

import copy
from decimal import Decimal
from types import SimpleNamespace

from django.db.models import Q

from ..models import (
    PayrollSettings,
    CompanyStatutorySettings,
    EmployeeSalaryAssignment,
)
from .common import (
    ZERO,
    ONE,
    STATUTORY_COMPONENT_ROLES,
    q2,
    validate_employee_for_payroll,
)
from .computation import (
    _load_structure_entries,
    _resolve_component_amounts,
    gross_package_warning,
    _compute_pf,
    _compute_esi,
    _compute_pt,
    _compute_lwf,
    apply_late_deduction,
    compute_vpf,
    vpf_line_item,
)

COUNT_FIELDS = (
    "present_days",
    "half_days",
    "absent_days",
    "paid_leave_days",
    "unpaid_leave_days",
    "holiday_days",
    "weekly_off_days",
    "not_employed_days",
)
VALID_MODES = ("SIMPLE", "FULL")
VALID_BASES = ("CALENDAR_DAYS", "FIXED_30", "WORKING_DAYS")


def _jsonable(value):
    """Decimals become strings, like every other payroll response."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def simulate_payslip(
    *,
    organization,
    period_start,
    period_end,
    counts_in,
    overtime_hours=ZERO,
    late_minutes=0,
    employee=None,
    salary_structure=None,
    payslip_mode=None,
    salary_basis=None,
    monthly_gross=None,
    annual_ctc=None,
):
    """
    counts_in: dict with any of COUNT_FIELDS (missing = 0) and optionally
    working_days (default: present + half + absent + paid leave + unpaid leave).

    Batch 3: monthly_gross or annual_ctc (optional) drives the structure as a
    template; without them the employee's assignment package is used when it
    has one, otherwise the structure amounts as before. The result also has
    "ctc_breakup".

    Raises ValueError with a readable message for bad input / configuration.
    """
    if period_end < period_start:
        raise ValueError("Period end cannot be before period start.")

    settings = PayrollSettings.objects.filter(organization=organization).first()
    if settings is None:
        raise ValueError("Payroll settings are not configured for this organization.")

    # Work on a copy: the stored settings row is never touched.
    settings = copy.copy(settings)
    if payslip_mode:
        if payslip_mode not in VALID_MODES:
            raise ValueError("payslip_mode must be SIMPLE or FULL.")
        settings.payslip_mode = payslip_mode
    if salary_basis:
        if salary_basis not in VALID_BASES:
            raise ValueError("salary_basis must be CALENDAR_DAYS, FIXED_30 or WORKING_DAYS.")
        settings.salary_basis = salary_basis

    # ---- Salary structure: given, or the employee's assignment for the period ----
    structure = salary_structure
    if structure is None:
        if employee is None:
            raise ValueError("Select an employee or a salary structure.")
        assignment = (
            EmployeeSalaryAssignment.objects.filter(
                organization=organization,
                employee=employee,
                effective_from__lte=period_end,
            )
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=period_start))
            .select_related("salary_structure")
            .order_by("-effective_from")
            .first()
        )
        if assignment is None:
            raise ValueError(
                f"No salary assignment found for {employee.employee_code} "
                f"covering {period_start} to {period_end}."
            )
        structure = assignment.salary_structure
        if monthly_gross is None and annual_ctc is None:
            monthly_gross = assignment.monthly_gross

    if annual_ctc is not None and monthly_gross is None:
        monthly_gross = monthly_gross_from_annual_ctc(
            organization, structure, annual_ctc, as_of=period_end, settings=settings,
        )["monthly_gross"]

    if settings.payslip_mode == "FULL" and employee is None:
        raise ValueError(
            "Select an employee for FULL mode: statutory deductions depend on the employee."
        )

    # ---- Counts ----
    counts = {}
    for key in COUNT_FIELDS:
        value = Decimal(str(counts_in.get(key, 0) or 0))
        if value < ZERO:
            raise ValueError(f"{key.replace('_', ' ').capitalize()} cannot be negative.")
        counts[key] = value

    if counts_in.get("working_days") not in (None, ""):
        working_days = Decimal(str(counts_in["working_days"]))
    else:
        working_days = (
            counts["present_days"] + counts["half_days"] + counts["absent_days"]
            + counts["paid_leave_days"] + counts["unpaid_leave_days"]
        )
    counts["working_days"] = working_days
    # Only used by the WORKING_DAYS basis for days outside employment.
    counts["not_employed_working_days"] = counts["not_employed_days"]

    period_days = Decimal((period_end - period_start).days + 1)
    day_total = sum(
        (counts[k] for k in (
            "present_days", "half_days", "absent_days", "paid_leave_days",
            "unpaid_leave_days", "holiday_days", "weekly_off_days", "not_employed_days",
        )),
        ZERO,
    )
    warnings = []
    if day_total != period_days:
        warnings.append(
            f"The days entered add up to {day_total.normalize():f}, but the period has "
            f"{period_days:f} days. Check the counts."
        )

    overtime_hours = Decimal(str(overtime_hours or 0))
    if overtime_hours < ZERO:
        raise ValueError("Overtime hours cannot be negative.")
    overtime_minutes = int((overtime_hours * Decimal("60")).to_integral_value())
    try:
        late_minutes = int(late_minutes or 0)
    except (TypeError, ValueError):
        raise ValueError("late_minutes must be a whole number.")
    if late_minutes < 0:
        raise ValueError("Late minutes cannot be negative.")

    stand_in = employee or SimpleNamespace(employee_code="(calculator)", work_state=None)

    if settings.payslip_mode == "FULL" and not CompanyStatutorySettings.objects.filter(
        organization=organization
    ).exists():
        warnings.append(
            "Statutory settings are not configured for this organization, so PF, ESI, PT and LWF are 0."
        )

    result = _build_payslip(
        stand_in, organization, settings, structure, period_start, period_end,
        monthly_gross=monthly_gross,
        counts=counts,
        overtime_minutes=overtime_minutes,
        late_minutes=late_minutes,
        warnings=warnings,
        requires_review=False,
        sources={},
        notes=[],
    )
    result.pop("requires_review", None)

    data = _jsonable(result)
    data["settings_used"] = {
        "payslip_mode": settings.payslip_mode,
        "salary_basis": settings.salary_basis,
        "absent_deduction_multiplier": str(settings.absent_deduction_multiplier),
        "half_day_deduction_multiplier": str(settings.half_day_deduction_multiplier),
        "unpaid_leave_multiplier": str(settings.unpaid_leave_multiplier),
        "overtime_enabled": bool(settings.overtime_enabled),
        "overtime_rate_multiplier": str(settings.overtime_rate_multiplier),
        "late_deduction_enabled": bool(settings.late_deduction_enabled),
        "late_deduction_multiplier": str(settings.late_deduction_multiplier),
        "standard_work_hours_per_day": str(settings.standard_work_hours_per_day),
    }
    data["period"] = {
        "period_start": str(period_start),
        "period_end": str(period_end),
        "period_days": str(period_days),
    }
    data["structure"] = {"id": getattr(structure, "id", None), "name": getattr(structure, "name", "")}
    data["ctc_breakup"] = _jsonable(compute_ctc_breakup(
        organization, structure, monthly_gross, as_of=period_end, settings=settings,
    ))
    return data


# =========================================================
# PAYSLIP ARITHMETIC (copy of the tail of compute_payslip_data)
# =========================================================

def _build_payslip(
    employee, organization, settings, structure, period_start, period_end,
    *, counts, overtime_minutes, warnings, requires_review, sources, notes,
    late_minutes=0,
    monthly_gross=None,
):
    """
    Everything after attendance is known: base days, loss of pay, overtime,
    statutory (FULL mode) and the payslip dict. Reads settings / statutory
    rows but writes nothing.
    """
    # ---- Base days for per-day rate ----
    period_days = Decimal((period_end - period_start).days + 1)
    not_employed_days = counts.get("not_employed_days", ZERO)
    not_employed_working = counts.get("not_employed_working_days", ZERO)

    if settings.salary_basis == "FIXED_30":
        base_days = Decimal("30")
    elif settings.salary_basis == "WORKING_DAYS":
        # Working days of the WHOLE period, including any days before joining
        # / after exit, so the per-day rate does not inflate for part-month staff.
        base_days = counts["working_days"] + not_employed_working
        if base_days <= ZERO:
            base_days = Decimal("30")
    else:  # CALENDAR_DAYS
        base_days = period_days

    # Days before joining / after resignation are unpaid.
    if settings.salary_basis == "WORKING_DAYS":
        not_employed_equiv = not_employed_working
    elif period_days > ZERO:
        not_employed_equiv = base_days * not_employed_days / period_days
    else:
        not_employed_equiv = ZERO

    # ---- Component amounts ----
    component_amounts, entries = _resolve_component_amounts(structure, monthly_gross=monthly_gross)
    package_warning = gross_package_warning(structure, monthly_gross, component_amounts, entries)
    if package_warning:
        warnings.append(package_warning)

    # ---- Full gross (non-statutory earnings only) ----
    full_gross = ZERO
    for entry in entries:
        comp = entry.salary_component
        if comp.component_type != "EARNING":
            continue
        if comp.component_role in STATUTORY_COMPONENT_ROLES:
            continue
        full_gross += component_amounts.get(comp.code, ZERO)
    full_gross = q2(full_gross)

    if full_gross <= ZERO:
        raise ValueError(
            f"Employee {employee.employee_code}: salary structure "
            f"'{structure.name}' has no non-statutory earnings. "
            f"Fix the structure before running payroll."
        )

    # ---- Per-day rate (display + overtime base) ----
    per_day_rate = q2(full_gross / base_days) if base_days > ZERO else ZERO

    # ---- Loss of Pay ----
    absence_equivalent = (
        counts["absent_days"] * settings.absent_deduction_multiplier
        + counts["half_days"] * settings.half_day_deduction_multiplier
        + counts["unpaid_leave_days"] * settings.unpaid_leave_multiplier
    )
    effective_absent_equivalent = absence_equivalent + not_employed_equiv

    # Use the unrounded rate so that "all days lost" deducts exactly the
    # gross, and never more than the gross.
    if base_days > ZERO:
        lop_amount = q2(full_gross * effective_absent_equivalent / base_days)
    else:
        lop_amount = ZERO
    if lop_amount > full_gross:
        lop_amount = full_gross

    # ---- Earned ratio (drives earned statutory base) ----
    paid_days_equivalent = base_days - effective_absent_equivalent
    if paid_days_equivalent < ZERO:
        paid_days_equivalent = ZERO
    earned_ratio = (
        paid_days_equivalent / base_days if base_days > ZERO else ZERO
    )
    if earned_ratio > ONE:
        earned_ratio = ONE

    # ---- Overtime ----
    overtime_hours = q2(Decimal(overtime_minutes) / Decimal("60"))
    overtime_amount = ZERO
    overtime_rate_per_hour = ZERO

    if settings.overtime_enabled and overtime_hours > ZERO:
        divisor = settings.standard_work_hours_per_day or Decimal("8")
        hourly_base = q2(per_day_rate / divisor) if divisor > ZERO else ZERO
        overtime_rate_per_hour = q2(
            hourly_base * settings.overtime_rate_multiplier
        )
        overtime_amount = q2(overtime_hours * overtime_rate_per_hour)

    # ---- Statutory (FULL mode only) ----
    statutory_settings = CompanyStatutorySettings.objects.filter(
        organization=organization
    ).first()

    is_full = settings.payslip_mode == "FULL"

    pf_result = {
        "pf_employee": ZERO, "pf_employer": ZERO,
        "eps": ZERO, "edli": ZERO,
    }
    esi_result = {"esi_employee": ZERO, "esi_employer": ZERO}
    lwf_result = {"lwf_employee": ZERO, "lwf_employer": ZERO}
    vpf_amount = ZERO
    pt_amount = ZERO
    pf_eligible_earned = ZERO
    esi_eligible_earned = ZERO

    if is_full and statutory_settings is not None:
        validate_employee_for_payroll(employee, statutory_settings)

        pf_eligible_full = ZERO
        esi_eligible_full = ZERO
        for entry in entries:
            comp = entry.salary_component
            if comp.component_type != "EARNING":
                continue
            amount = component_amounts.get(comp.code, ZERO)
            if comp.is_pf_eligible:
                pf_eligible_full += amount
            if comp.is_esi_eligible:
                esi_eligible_full += amount

        pf_eligible_earned = q2(pf_eligible_full * earned_ratio)
        esi_eligible_earned = q2(esi_eligible_full * earned_ratio)

        pf_result = _compute_pf(
            statutory_settings, pf_eligible_earned, period_end,
        )
        vpf_amount = compute_vpf(statutory_settings, employee, pf_result)
        esi_result = _compute_esi(
            statutory_settings, esi_eligible_earned, period_end,
        )
        lwf_result = _compute_lwf(
            statutory_settings, pf_eligible_earned, period_end,
        )
        pt_amount = _compute_pt(
            statutory_settings,
            employee,
            q2(full_gross - lop_amount),
            period_end,
            period_end.month,
        )

    # ---- Line items ----
    line_items = []

    if is_full:
        # Earnings: individual non-statutory components
        for entry in entries:
            comp = entry.salary_component
            if comp.component_type != "EARNING":
                continue
            if comp.component_role in STATUTORY_COMPONENT_ROLES:
                continue
            amount = component_amounts.get(comp.code, ZERO)
            if amount == ZERO:
                continue
            line_items.append({
                "component_code": comp.code,
                "component_name": comp.name,
                "component_type": "EARNING",
                "amount": amount,
                "calculation_details": {
                    "full_amount": str(amount),
                    "calculation_type": comp.calculation_type,
                },
            })

        if overtime_amount > ZERO:
            line_items.append({
                "component_code": "OT",
                "component_name": "Overtime",
                "component_type": "EARNING",
                "amount": overtime_amount,
                "calculation_details": {
                    "hours": str(overtime_hours),
                    "rate_per_hour": str(overtime_rate_per_hour),
                },
            })

        if lop_amount > ZERO:
            line_items.append({
                "component_code": "LOP",
                "component_name": "Loss of Pay",
                "component_type": "LOP",
                "amount": lop_amount,
                "calculation_details": {
                    "absent_days": str(counts["absent_days"]),
                    "half_days": str(counts["half_days"]),
                    "unpaid_leave_days": str(counts["unpaid_leave_days"]),
                    "not_employed_days": str(not_employed_days),
                    "per_day_rate": str(per_day_rate),
                },
            })

        # Non-statutory deductions from structure (prorated by earned ratio)
        for entry in entries:
            comp = entry.salary_component
            if comp.component_type != "DEDUCTION":
                continue
            if comp.component_role in STATUTORY_COMPONENT_ROLES:
                continue
            amount = component_amounts.get(comp.code, ZERO)
            if amount == ZERO:
                continue
            prorated = q2(amount * earned_ratio)
            line_items.append({
                "component_code": comp.code,
                "component_name": comp.name,
                "component_type": "DEDUCTION",
                "amount": prorated,
                "calculation_details": {
                    "full_amount": str(amount),
                    "earned_ratio": str(earned_ratio),
                },
            })

        # Statutory deductions
        if pf_result["pf_employee"] > ZERO:
            line_items.append({
                "component_code": "PF",
                "component_name": "Provident Fund (Employee)",
                "component_type": "DEDUCTION",
                "amount": pf_result["pf_employee"],
                "calculation_details": {
                    "pf_eligible_earned": str(pf_eligible_earned),
                },
            })

        if vpf_amount > ZERO:
            line_items.append(vpf_line_item(vpf_amount, employee, pf_result))

        if esi_result["esi_employee"] > ZERO:
            line_items.append({
                "component_code": "ESI",
                "component_name": "ESI (Employee)",
                "component_type": "DEDUCTION",
                "amount": esi_result["esi_employee"],
                "calculation_details": {
                    "esi_eligible_earned": str(esi_eligible_earned),
                },
            })

        if pt_amount > ZERO:
            state_used = employee.work_state or statutory_settings.pt_state
            line_items.append({
                "component_code": "PT",
                "component_name": "Professional Tax",
                "component_type": "DEDUCTION",
                "amount": pt_amount,
                "calculation_details": {
                    "pt_state": (
                        getattr(state_used, "state_name", None)
                        if state_used else None
                    ),
                    "is_february": period_end.month == 2,
                },
            })

        if lwf_result["lwf_employee"] > ZERO:
            line_items.append({
                "component_code": "LWF",
                "component_name": "Labour Welfare Fund (Employee)",
                "component_type": "DEDUCTION",
                "amount": lwf_result["lwf_employee"],
                "calculation_details": {},
            })
    else:
        # SIMPLE mode: single gross earning + LOP only
        line_items.append({
            "component_code": "GROSS",
            "component_name": "Gross Salary",
            "component_type": "EARNING",
            "amount": full_gross,
            "calculation_details": {"source": "salary_structure_total"},
        })

        if overtime_amount > ZERO:
            line_items.append({
                "component_code": "OT",
                "component_name": "Overtime",
                "component_type": "EARNING",
                "amount": overtime_amount,
                "calculation_details": {
                    "hours": str(overtime_hours),
                    "rate_per_hour": str(overtime_rate_per_hour),
                },
            })

        if lop_amount > ZERO:
            line_items.append({
                "component_code": "LOP",
                "component_name": "Loss of Pay",
                "component_type": "LOP",
                "amount": lop_amount,
                "calculation_details": {
                    "absent_days": str(counts["absent_days"]),
                    "half_days": str(counts["half_days"]),
                    "unpaid_leave_days": str(counts["unpaid_leave_days"]),
                    "not_employed_days": str(not_employed_days),
                    "per_day_rate": str(per_day_rate),
                },
            })

    # ---- Late mark deduction (after every other line, capped at net 0) ----
    late_amount = apply_late_deduction(line_items, settings, per_day_rate, late_minutes)

    gross_total = q2(sum(
        li["amount"] for li in line_items
        if li["component_type"] == "EARNING"
    ))
    deductions_total = q2(sum(
        li["amount"] for li in line_items
        if li["component_type"] in {"DEDUCTION", "LOP"}
    ))
    net = q2(gross_total - deductions_total)

    # ---- Breakdown audit ----
    breakdown = {
        "payslip_mode": settings.payslip_mode,
        "salary_basis": settings.salary_basis,
        "base_days": str(base_days),
        "per_day_rate": str(per_day_rate),
        "full_gross": str(full_gross),
        "earned_ratio": str(earned_ratio),
        "effective_absent_equivalent": str(effective_absent_equivalent),
        "not_employed_days": str(not_employed_days),
        "payable_days": str(q2(paid_days_equivalent)),
        "working_days": str(counts["working_days"]),
        "attendance_notes": notes,
        "component_amounts": {
            code: str(amount) for code, amount in component_amounts.items()
        },
        "attendance_sources": {
            key: str(value) for key, value in sources.items()
        },
        "late_minutes": late_minutes,
        "late_deduction": str(late_amount),
        "employer_costs": {
            "pf_employer": str(pf_result["pf_employer"]),
            "eps": str(pf_result["eps"]),
            "edli": str(pf_result["edli"]),
            "esi_employer": str(esi_result["esi_employer"]),
            "lwf_employer": str(lwf_result["lwf_employer"]),
        },
        "warnings": warnings,
    }

    return {
        # Attendance snapshot
        "present_days": counts["present_days"],
        "half_days": counts["half_days"],
        "absent_days": counts["absent_days"],
        "paid_leave_days": counts["paid_leave_days"],
        "unpaid_leave_days": counts["unpaid_leave_days"],
        "holiday_days": counts["holiday_days"],
        "weekly_off_days": counts["weekly_off_days"],
        "overtime_hours": overtime_hours,
        "late_minutes": late_minutes,

        # Salary snapshot
        "monthly_salary": full_gross,
        "per_day_rate": per_day_rate,

        # Statutory snapshot
        "pf_employee": pf_result["pf_employee"],
        "vpf_employee": vpf_amount,
        "pf_employer": pf_result["pf_employer"],
        "eps": pf_result["eps"],
        "edli": pf_result["edli"],
        "esi_employee": esi_result["esi_employee"],
        "esi_employer": esi_result["esi_employer"],
        "pt": pt_amount,
        "tds": ZERO,
        "lwf_employee": lwf_result["lwf_employee"],
        "lwf_employer": lwf_result["lwf_employer"],
        "other_deductions": ZERO,

        # Totals
        "gross_earnings": gross_total,
        "total_deductions": deductions_total,
        "net": net,

        # Line items & audit
        "line_items": line_items,
        "requires_review": requires_review or bool(warnings),
        "warnings": warnings,
        "breakdown": breakdown,
    }


# =========================================================
# CTC (batch 3)
# =========================================================
# Employer cost per month = PF employer (its 12 % already contains the EPS
# split, so EPS is not added again) + EDLI + ESI employer + LWF employer,
# computed on a full month (no loss of pay) and only in FULL payslip mode
# with the schemes enabled in statutory settings.
# annual CTC = 12 x (monthly gross + employer cost) when
# PayrollSettings.ctc_includes_employer_contributions is True, else 12 x gross.

def compute_ctc_breakup(organization, structure, monthly_gross=None, as_of=None, settings=None, entries=None):
    """Monthly / annual package for a structure (optionally at a given gross)."""
    from django.utils import timezone

    if settings is None:
        settings = PayrollSettings.objects.filter(organization=organization).first()
        if settings is None:
            raise ValueError("Payroll settings are not configured for this organization.")
    as_of = as_of or timezone.localdate()
    if entries is None:
        entries = _load_structure_entries(structure)

    amounts, entries = _resolve_component_amounts(structure, monthly_gross=monthly_gross, entries=entries)

    earnings, pf_base, esi_base = [], ZERO, ZERO
    for entry in entries:
        comp = entry.salary_component
        if comp.component_type != "EARNING" or comp.component_role in STATUTORY_COMPONENT_ROLES:
            continue
        amount = amounts.get(comp.code, ZERO)
        earnings.append({"code": comp.code, "name": comp.name, "monthly": amount, "annual": q2(amount * 12)})
        if comp.is_pf_eligible:
            pf_base += amount
        if comp.is_esi_eligible:
            esi_base += amount
    gross = q2(sum((e["monthly"] for e in earnings), ZERO))

    employer = {"pf_employer": ZERO, "edli": ZERO, "esi_employer": ZERO, "lwf_employer": ZERO}
    statutory = CompanyStatutorySettings.objects.filter(organization=organization).first()
    if settings.payslip_mode == "FULL" and statutory is not None:
        pf = _compute_pf(statutory, q2(pf_base), as_of)
        esi = _compute_esi(statutory, q2(esi_base), as_of)
        lwf = _compute_lwf(statutory, q2(pf_base), as_of)
        employer = {
            "pf_employer": pf["pf_employer"],
            "edli": pf["edli"],
            "esi_employer": esi["esi_employer"],
            "lwf_employer": lwf["lwf_employer"],
        }
    employer_total = q2(sum(employer.values(), ZERO))
    include = bool(getattr(settings, "ctc_includes_employer_contributions", True))
    monthly_ctc = q2(gross + (employer_total if include else ZERO))

    return {
        "monthly_gross": gross,
        "annual_gross": q2(gross * 12),
        "earnings": earnings,
        "employer_contributions": {**employer, "total": employer_total},
        "ctc_includes_employer_contributions": include,
        "monthly_ctc": monthly_ctc,
        "annual_ctc": q2(monthly_ctc * 12),
    }


def monthly_gross_from_annual_ctc(organization, structure, annual_ctc, as_of=None, settings=None):
    """
    Monthly gross that gives `annual_ctc` with this structure (binary search
    to the paisa; employer cost depends on the gross through PF/ESI bases).
    Returns the breakup at that gross plus "difference" (annual) when an
    exact match is impossible (e.g. around the ESI ceiling).
    """
    target = q2(Decimal(str(annual_ctc)))
    if target <= ZERO:
        raise ValueError("annual_ctc must be greater than zero.")
    entries = _load_structure_entries(structure)

    def ctc_at(gross):
        return compute_ctc_breakup(organization, structure, gross, as_of=as_of, settings=settings, entries=entries)

    low, high = ZERO, q2(target / 12)
    best = ctc_at(high)
    for _ in range(60):
        mid = q2((low + high) / 2)
        if mid in (low, high):
            break
        result = ctc_at(mid)
        if result["annual_ctc"] > target:
            high = mid
        else:
            low, best = mid, result
    for candidate in (low, high):
        result = ctc_at(candidate)
        if abs(result["annual_ctc"] - target) < abs(best["annual_ctc"] - target):
            best = result
    best = dict(best)
    best["requested_annual_ctc"] = target
    best["difference"] = q2(best["annual_ctc"] - target)
    return best


# =========================================================
# DEFAULT PACKAGE FROM THE STRUCTURE (batch 17)
# =========================================================

def structure_needs_gross(structure, entries=None):
    """
    True when the structure cannot give a salary on its own: it has a
    balancing component, or a PERCENTAGE earning with no base component
    (a % of monthly gross). Such structures need annual_ctc / monthly_gross.
    """
    if entries is None:
        entries = _load_structure_entries(structure)
    for entry in entries:
        comp = entry.salary_component
        if getattr(entry, "is_balancing", False):
            return True
        if comp.calculation_type == "PERCENTAGE" and comp.percentage_of_component_id is None:
            return True
    return False


def default_package_from_structure(organization, structure, as_of=None):
    """
    Batch 17: package for an assignment sent without annual_ctc and
    monthly_gross. Same calculation as compute_ctc_breakup with no gross:
      monthly_gross = sum of the structure's earnings (fixed amounts and
                      % of other components; statutory roles excluded)
      annual_ctc    = 12 x (gross + employer PF / EDLI / ESI / LWF in FULL
                      mode, when ctc_includes_employer_contributions), else
                      12 x gross. No payroll settings yet -> 12 x gross.
    Returns {"annual_ctc", "monthly_gross"}. Raises ValueError when the
    structure needs a gross figure or gives no salary.
    """
    entries = _load_structure_entries(structure)
    if structure_needs_gross(structure, entries):
        raise ValueError(
            f"Structure '{structure.name}' is based on monthly gross (balancing / % of gross "
            f"component). Send annual_ctc or monthly_gross."
        )
    settings = PayrollSettings.objects.filter(organization=organization).first()
    if settings is not None:
        breakup = compute_ctc_breakup(organization, structure, None, as_of=as_of, settings=settings, entries=entries)
        gross, ctc = breakup["monthly_gross"], breakup["annual_ctc"]
    else:
        amounts, entries = _resolve_component_amounts(structure, monthly_gross=None, entries=entries)
        gross = q2(sum(
            (amounts.get(e.salary_component.code, ZERO) for e in entries
             if e.salary_component.component_type == "EARNING"
             and e.salary_component.component_role not in STATUTORY_COMPONENT_ROLES),
            ZERO,
        ))
        ctc = q2(gross * 12)
    if gross <= ZERO:
        raise ValueError(
            f"Structure '{structure.name}' gives no salary on its own. Send annual_ctc or monthly_gross."
        )
    return {"annual_ctc": ctc, "monthly_gross": gross}

