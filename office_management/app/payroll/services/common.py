"""
Shared constants, helpers, statutory lookups, cycle computation,
and employee required-field validation.

No imports from other payroll service files — safe leaf module.
"""

from datetime import date as date_type, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q

from app.audit.services import log_activity

from ..models import StatutoryRateConfig, StatutorySlab


ZERO = Decimal("0.00")
ONE = Decimal("1.00")
TWOPLACES = Decimal("0.01")
HUNDRED = Decimal("100")

# Employee statuses included in payroll runs.
PAYROLL_ELIGIBLE_STATUSES = ["ACTIVE", "ON_LEAVE"]

# Roles reserved for statutory computation — never treated as payable earnings.
STATUTORY_COMPONENT_ROLES = {
    "PF_EMPLOYEE", "PF_EMPLOYER",
    "ESI_EMPLOYEE", "ESI_EMPLOYER",
    "PT", "TDS", "LWF",
}


# =========================================================
# NUMERIC / AUDIT HELPERS
# =========================================================

def q2(value):
    """Round a Decimal-ish value to 2 places, half-up. None -> ZERO."""
    if value is None:
        return ZERO
    return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def audit_log(**kwargs):
    """Never let audit failure break payroll."""
    try:
        log_activity(**kwargs)
    except Exception:
        pass


# =========================================================
# STATUTORY RATE / SLAB LOOKUPS
# =========================================================

def get_statutory_rate(component_code, as_of_date, organization=None):
    """
    Return StatutoryRateConfig in effect on `as_of_date`.

    Org-specific override is preferred over the federal default
    (organization IS NULL). Returns None when no config applies.
    """
    qs = StatutoryRateConfig.objects.filter(
        component_code=component_code,
        effective_from__lte=as_of_date,
    ).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gte=as_of_date)
    )

    if organization is not None:
        org_config = (
            qs.filter(organization=organization)
            .order_by("-effective_from")
            .first()
        )
        if org_config:
            return org_config

    return (
        qs.filter(organization__isnull=True)
        .order_by("-effective_from")
        .first()
    )


def get_pt_slab_amount(state, monthly_gross, as_of_date, is_february=False):
    """
    Return PT amount for a state, gross and month.

    February logic:
      - If a Feb override slab exists for the matching income band, PT becomes
        normal_slab.fixed_amount + feb_override.additional_amount.
      - Otherwise PT is normal_slab.fixed_amount.
    """
    if state is None:
        return ZERO

    base_qs = StatutorySlab.objects.filter(
        slab_type="PT",
        state=state,
        effective_from__lte=as_of_date,
    ).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gte=as_of_date)
    ).filter(
        income_from__lte=monthly_gross,
    ).filter(
        Q(income_to__isnull=True) | Q(income_to__gte=monthly_gross),
    )

    normal_slab = (
        base_qs.filter(is_february_override=False)
        .order_by("-effective_from")
        .first()
    )

    if normal_slab is None:
        return ZERO

    base_amount = normal_slab.fixed_amount or ZERO

    if not is_february:
        return q2(base_amount)

    feb_override = (
        base_qs.filter(is_february_override=True)
        .order_by("-effective_from")
        .first()
    )

    if feb_override is None:
        return q2(base_amount)

    return q2(base_amount + (feb_override.additional_amount or ZERO))


# =========================================================
# CYCLE PERIOD
# =========================================================

def _add_months(d, months):
    """Add N months to a date, preserving day-of-month (safe for 1-28)."""
    month = d.month + months
    year = d.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    return d.replace(year=year, month=month, day=d.day)


def compute_cycle_period(cycle_start_day, reference=None):
    """
    Compute (period_start, period_end) for a monthly payroll cycle.

    reference:
      - None or "current"  -> cycle containing today
      - "YYYY-MM"          -> cycle that STARTS in that month
      - date object        -> cycle containing that date
    """
    if not (1 <= cycle_start_day <= 28):
        raise ValueError("cycle_start_day must be between 1 and 28.")

    if reference is None or reference == "current":
        ref_date = date_type.today()
        if ref_date.day >= cycle_start_day:
            period_start = ref_date.replace(day=cycle_start_day)
        else:
            prev_month_end = ref_date.replace(day=1) - timedelta(days=1)
            period_start = prev_month_end.replace(day=cycle_start_day)

    elif isinstance(reference, str):
        parts = reference.split("-")
        if len(parts) != 2:
            raise ValueError(
                "reference must be None, 'current', 'YYYY-MM', or a date."
            )
        try:
            year, month = int(parts[0]), int(parts[1])
        except ValueError:
            raise ValueError(
                "reference must be None, 'current', 'YYYY-MM', or a date."
            )
        if not (1 <= month <= 12):
            raise ValueError("Invalid month in reference.")
        period_start = date_type(year, month, cycle_start_day)

    elif isinstance(reference, date_type):
        if reference.day >= cycle_start_day:
            period_start = reference.replace(day=cycle_start_day)
        else:
            prev_month_end = reference.replace(day=1) - timedelta(days=1)
            period_start = prev_month_end.replace(day=cycle_start_day)

    else:
        raise ValueError(
            "reference must be None, 'current', 'YYYY-MM', or a date."
        )

    period_end = _add_months(period_start, 1) - timedelta(days=1)
    return period_start, period_end


# =========================================================
# EMPLOYEE REQUIRED-FIELD VALIDATION (FULL mode only)
# =========================================================

def validate_employee_for_payroll(employee, statutory_settings):
    """
    Raise ValueError if the employee is missing fields required by the
    organization's enabled statutory schemes. Only called in FULL mode.
    """
    code = employee.employee_code
    missing = []

    if not employee.first_name or not employee.last_name:
        missing.append("first_name/last_name")
    if not employee.organization_id:
        missing.append("organization")

    if missing:
        raise ValueError(
            f"Employee {code}: profile incomplete "
            f"(missing {', '.join(missing)})."
        )

    if statutory_settings is None:
        return

    if statutory_settings.is_pf_applicable:
        if not employee.pf_uan:
            raise ValueError(
                f"Employee {code}: PF UAN is required because PF is "
                f"enabled. Update the employee profile."
            )
        if not employee.pan_number:
            raise ValueError(
                f"Employee {code}: PAN is required because PF is "
                f"enabled. Update the employee profile."
            )

    if statutory_settings.is_esi_applicable:
        if not employee.esi_ip_number:
            raise ValueError(
                f"Employee {code}: ESI IP number is required because ESI "
                f"is enabled. Update the employee profile."
            )

    if statutory_settings.is_pt_applicable:
        # Allow org default pt_state as a fallback when the employee's
        # work_state is not set.
        if not employee.work_state_id and not statutory_settings.pt_state_id:
            raise ValueError(
                f"Employee {code}: work state is required because PT is "
                f"enabled. Update the employee profile or set the "
                f"organization's default PT state."
            )

    if statutory_settings.is_tds_applicable:
        if not employee.pan_number:
            raise ValueError(
                f"Employee {code}: PAN is required because TDS is "
                f"enabled. Update the employee profile."
            )
