"""
Statutory computations, component resolution, and compute_payslip_data.

Imports common + attendance only. No cycle back to processing/payments.
"""

from decimal import Decimal

from django.db.models import Q

from ..models import (
    PayrollSettings,
    CompanyStatutorySettings,
    EmployeeSalaryAssignment,
)
from .common import (
    ZERO,
    ONE,
    HUNDRED,
    STATUTORY_COMPONENT_ROLES,
    q2,
    get_statutory_rate,
    get_pt_slab_amount,
    validate_employee_for_payroll,
)
from .attendance import compute_attendance_counts


# =========================================================
# STATUTORY COMPUTATIONS (FULL mode only)
# =========================================================

def _require_rate(component_code, as_of_date, organization, scheme_label):
    """
    Fetch a rate config for a scheme that is toggled on for the org.
    Raise a clear ValueError if the super admin has not seeded a rate for
    the period — this is a configuration error, not a silent zero.
    """
    cfg = get_statutory_rate(
        component_code, as_of_date, organization=organization,
    )
    if cfg is None:
        raise ValueError(
            f"{scheme_label} is enabled for this organization but no rate "
            f"is configured for {as_of_date}. Contact your administrator."
        )
    return cfg


def _compute_pf(statutory_settings, pf_eligible_earned, as_of_date):
    """
    PF / EPS / EDLI computed on the earned PF-eligible wage.
    PF admin charges are establishment-level and handled by the CA, not here.
    """
    result = {
        "pf_employee": ZERO,
        "pf_employer": ZERO,
        "eps": ZERO,
        "edli": ZERO,
    }

    if statutory_settings is None or not statutory_settings.is_pf_applicable:
        return result

    org = statutory_settings.organization
    base = pf_eligible_earned

    emp_cfg = _require_rate("PF_EMPLOYEE", as_of_date, org, "PF")
    wage = base if emp_cfg.wage_ceiling is None else min(base, emp_cfg.wage_ceiling)
    result["pf_employee"] = q2(wage * emp_cfg.rate_percentage / HUNDRED)

    er_cfg = _require_rate("PF_EMPLOYER", as_of_date, org, "PF")
    wage = base if er_cfg.wage_ceiling is None else min(base, er_cfg.wage_ceiling)
    result["pf_employer"] = q2(wage * er_cfg.rate_percentage / HUNDRED)

    eps_cfg = _require_rate("EPS", as_of_date, org, "EPS")
    wage = base if eps_cfg.wage_ceiling is None else min(base, eps_cfg.wage_ceiling)
    result["eps"] = q2(wage * eps_cfg.rate_percentage / HUNDRED)

    edli_cfg = _require_rate("EDLI", as_of_date, org, "EDLI")
    wage = base if edli_cfg.wage_ceiling is None else min(base, edli_cfg.wage_ceiling)
    result["edli"] = q2(wage * edli_cfg.rate_percentage / HUNDRED)

    return result


def _compute_esi(statutory_settings, esi_eligible_earned, as_of_date):
    """
    ESI employee + employer.
    Skipped entirely when earned ESI wage exceeds the configured wage ceiling.
    """
    result = {"esi_employee": ZERO, "esi_employer": ZERO}

    if statutory_settings is None or not statutory_settings.is_esi_applicable:
        return result

    org = statutory_settings.organization

    emp_cfg = _require_rate("ESI_EMPLOYEE", as_of_date, org, "ESI")
    if emp_cfg.wage_ceiling is not None and esi_eligible_earned > emp_cfg.wage_ceiling:
        return result

    result["esi_employee"] = q2(
        esi_eligible_earned * emp_cfg.rate_percentage / HUNDRED
    )

    er_cfg = _require_rate("ESI_EMPLOYER", as_of_date, org, "ESI")
    result["esi_employer"] = q2(
        esi_eligible_earned * er_cfg.rate_percentage / HUNDRED
    )

    return result


def _compute_pt(statutory_settings, employee, gross_earned, as_of_date, month):
    """
    PT computed from the EMPLOYEE work state, falling back to the org default.
    Raise a clear configuration error when PT is enabled, a state exists,
    but no slab is configured for that state.
    """
    if statutory_settings is None or not statutory_settings.is_pt_applicable:
        return ZERO

    state = employee.work_state or statutory_settings.pt_state
    if state is None:
        return ZERO

    from ..models import StatutorySlab

    slabs_exist = (
        StatutorySlab.objects.filter(
            slab_type="PT",
            state=state,
            effective_from__lte=as_of_date,
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=as_of_date)
        ).exists()
    )

    if not slabs_exist:
        raise ValueError(
            f"PT is enabled and employee {employee.employee_code} is in "
            f"{getattr(state, 'state_name', state)}, but no PT slabs are "
            f"configured for that state. Contact your administrator."
        )

    return get_pt_slab_amount(
        state=state,
        monthly_gross=gross_earned,
        as_of_date=as_of_date,
        is_february=(month == 2),
    )


def _compute_lwf(statutory_settings, pf_eligible_earned, as_of_date):
    """
    LWF employee + employer.
    Uses StatutoryRateConfig (LWF_EMPLOYEE / LWF_EMPLOYER). If a rate
    config's rate_percentage is None, that side is treated as zero.
    """
    result = {"lwf_employee": ZERO, "lwf_employer": ZERO}

    if statutory_settings is None or not statutory_settings.is_lwf_applicable:
        return result

    org = statutory_settings.organization

    emp_cfg = _require_rate("LWF_EMPLOYEE", as_of_date, org, "LWF")
    if emp_cfg.rate_percentage is not None:
        result["lwf_employee"] = q2(
            pf_eligible_earned * emp_cfg.rate_percentage / HUNDRED
        )

    er_cfg = _require_rate("LWF_EMPLOYER", as_of_date, org, "LWF")
    if er_cfg.rate_percentage is not None:
        result["lwf_employer"] = q2(
            pf_eligible_earned * er_cfg.rate_percentage / HUNDRED
        )

    return result


# =========================================================
# COMPONENT RESOLUTION
# =========================================================

def _load_structure_entries(structure):
    return list(
        structure.components.select_related(
            "salary_component",
            "salary_component__percentage_of_component",
        ).all()
    )


def _is_gross_earning(comp):
    return comp.component_type == "EARNING" and comp.component_role not in STATUTORY_COMPONENT_ROLES


def _resolve_component_amounts(structure, monthly_gross=None, entries=None):
    """
    Return (resolved_dict, entries_list) for a salary structure.

    FIXED components use SalaryStructureComponent.amount.
    PERCENTAGE components apply SalaryStructureComponent.percentage against
    the referenced component's resolved amount. Multi-pass so chained
    percentage references resolve in a single call. Any unresolved
    percentage ends at zero (defensive; misconfig, not crash).

    Batch 3, only when monthly_gross is given (assignment / offer package):
      - a PERCENTAGE component without a base component is a % of monthly_gross;
      - the entry marked is_balancing gets monthly_gross minus every other
        gross earning (never below zero).
    Without monthly_gross the result is exactly as before.
    """
    if entries is None:
        entries = _load_structure_entries(structure)

    use_gross = monthly_gross is not None
    gross = q2(Decimal(str(monthly_gross))) if use_gross else None
    balancing = [e for e in entries if use_gross and getattr(e, "is_balancing", False)]
    balancing_codes = {e.salary_component.code for e in balancing}

    resolved = {}

    # Pass 1: fixed
    for entry in entries:
        comp = entry.salary_component
        if comp.code in balancing_codes:
            continue
        if comp.calculation_type == "FIXED":
            resolved[comp.code] = q2(entry.amount or ZERO)

    def percentage_passes():
        for _ in range(len(entries)):
            progress = False
            for entry in entries:
                comp = entry.salary_component
                if comp.calculation_type != "PERCENTAGE":
                    continue
                if comp.code in resolved or comp.code in balancing_codes:
                    continue
                base_comp = comp.percentage_of_component
                if base_comp is None:
                    base_amount = gross if use_gross else None
                    if base_amount is None:
                        resolved[comp.code] = ZERO
                        progress = True
                        continue
                else:
                    base_amount = resolved.get(base_comp.code)
                    if base_amount is None:
                        continue
                resolved[comp.code] = q2(
                    base_amount * (entry.percentage or ZERO) / HUNDRED
                )
                progress = True
            if not progress:
                break

    # Passes 2..N: percentage (bounded by entries count)
    percentage_passes()

    # Balancing earning: monthly gross minus every other gross earning.
    for entry in balancing:
        comp = entry.salary_component
        others = sum(
            (resolved.get(e.salary_component.code, ZERO) for e in entries
             if _is_gross_earning(e.salary_component) and e.salary_component.code not in balancing_codes),
            ZERO,
        )
        resolved[comp.code] = q2(max(gross - others, ZERO))
    if balancing:
        percentage_passes()  # components based on the balancing one (unusual)

    for entry in entries:
        comp = entry.salary_component
        resolved.setdefault(comp.code, ZERO)

    return resolved, entries


def gross_package_warning(structure, monthly_gross, component_amounts, entries):
    """
    Batch 3: warning text when the structure cannot reproduce the agreed
    monthly gross (no balancing earning, or fixed parts larger than the gross).
    None when it matches (to the rupee) or when no gross was agreed.
    """
    if monthly_gross is None:
        return None
    total = q2(sum(
        (component_amounts.get(e.salary_component.code, ZERO) for e in entries
         if _is_gross_earning(e.salary_component)),
        ZERO,
    ))
    agreed = q2(Decimal(str(monthly_gross)))
    if abs(total - agreed) <= ONE:
        return None
    return (
        f"Salary structure '{structure.name}' gives a monthly gross of {total} "
        f"but the agreed monthly gross is {agreed}. Mark one earning as the "
        f"balancing component, or adjust the fixed amounts."
    )


# =========================================================
# PAYSLIP COMPUTATION
# =========================================================

def apply_late_deduction(line_items, settings, per_day_rate, late_minutes):
    """
    Late mark deduction (PayrollSettings.late_deduction_enabled).

    amount = late_minutes x per-minute rate x late_deduction_multiplier
    per-minute rate = per-day rate / (standard_work_hours_per_day x 60)

    Appends a "LATE" DEDUCTION line and returns the amount. Capped so the
    net pay never goes below zero. Does not change PF / ESI / PT bases.
    """
    late_minutes = int(late_minutes or 0)
    if not getattr(settings, "late_deduction_enabled", False) or late_minutes <= 0:
        return ZERO
    hours = settings.standard_work_hours_per_day or Decimal("8")
    if hours <= ZERO or per_day_rate <= ZERO:
        return ZERO

    multiplier = settings.late_deduction_multiplier or ZERO
    rate_per_minute = per_day_rate / (hours * Decimal("60"))
    amount = q2(Decimal(late_minutes) * rate_per_minute * multiplier)

    earnings = sum((li["amount"] for li in line_items if li["component_type"] == "EARNING"), ZERO)
    deductions = sum((li["amount"] for li in line_items if li["component_type"] in {"DEDUCTION", "LOP"}), ZERO)
    room = q2(earnings - deductions)
    capped = amount > room
    if capped:
        amount = room if room > ZERO else ZERO
    if amount <= ZERO:
        return ZERO

    line_items.append({
        "component_code": "LATE",
        "component_name": "Late Deduction",
        "component_type": "DEDUCTION",
        "amount": amount,
        "calculation_details": {
            "late_minutes": str(late_minutes),
            "rate_per_minute": str(rate_per_minute.quantize(Decimal("0.0001"))),
            "rate_per_hour": str(q2(rate_per_minute * Decimal("60"))),
            "multiplier": str(multiplier),
            "capped_to_zero_net": capped,
        },
    })
    return amount


def compute_payslip_data(employee, organization, period_start, period_end):
    """
    Compute one employee's payslip. Returns a dict ready for persistence.

    Raises ValueError on configuration or employee-data problems; the
    caller (generate_payroll) turns this into an ERROR PayrollRecord.
    """
    settings = PayrollSettings.objects.filter(
        organization=organization
    ).first()
    if settings is None:
        raise ValueError(
            f"Payroll settings are not configured for organization "
            f"{organization.id}."
        )

    # ---- Salary assignment ----
    assignment = (
        EmployeeSalaryAssignment.objects.filter(
            organization=organization,
            employee=employee,
            effective_from__lte=period_end,
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=period_start)
        )
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

    # ---- Attendance ----
    attendance = compute_attendance_counts(
        employee, organization, period_start, period_end, settings,
    )
    counts = attendance["counts"]
    overtime_minutes = attendance["overtime_minutes"]
    late_minutes = int(attendance.get("late_minutes", 0) or 0)
    warnings = attendance["warnings"]
    requires_review = attendance["requires_review"]
    sources = attendance["sources"]
    notes = attendance.get("notes", [])

    # An assignment that does not cover the whole period would price the
    # whole period at this one structure. Flag it for review.
    if (
        assignment.effective_from > period_start
        or (assignment.effective_to is not None
            and assignment.effective_to < period_end)
    ):
        warnings.append(
            f"Salary assignment '{structure.name}' covers "
            f"{assignment.effective_from} to "
            f"{assignment.effective_to or 'open-ended'}, not the whole "
            f"period; the whole period was calculated with this structure. "
            f"Check the salary assignments."
        )

    # ---- Base days for per-day rate ----
    period_days = Decimal((period_end - period_start).days + 1)
    not_employed_days = counts.get("not_employed_days", ZERO)
    not_employed_working = counts.get("not_employed_working_days", ZERO)

    if (
        settings.salary_basis == "WORKING_DAYS"
        and not_employed_days > ZERO
        and not_employed_working <= ZERO
    ):
        warnings.append(
            f"Employee was not employed for {int(not_employed_days)} day(s) "
            f"but no scheduled working days were found for them (no shift "
            f"assigned?). Pay on the working-days basis may be overstated. "
            f"Assign a shift and recompute, or accept with a review note."
        )

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
    # Batch 3: an assignment with an agreed monthly gross drives the amounts.
    component_amounts, entries = _resolve_component_amounts(
        structure, monthly_gross=assignment.monthly_gross,
    )
    package_warning = gross_package_warning(
        structure, assignment.monthly_gross, component_amounts, entries,
    )
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
