"""
Payroll service package.

Public API re-exported here so callers do:
    from app.payroll.services import compute_payslip_data, generate_payroll

File responsibilities:
  - common.py       : constants, q2, audit_log, statutory lookups, cycle, validation
  - attendance.py   : leave map + day-by-day attendance classification
  - computation.py  : PF/ESI/PT/LWF, component resolution, compute_payslip_data
  - processing.py   : persistence, generate, finalize, recompute, manual deductions,
                      bulk assign/close
  - payments.py     : record_payment, update_payment_status, bulk_record_payment_for_run
"""

from .common import (
    ZERO,
    ONE,
    TWOPLACES,
    HUNDRED,
    PAYROLL_ELIGIBLE_STATUSES,
    STATUTORY_COMPONENT_ROLES,
    compute_cycle_period,
    get_statutory_rate,
    get_pt_slab_amount,
)

from .computation import compute_payslip_data

from .processing import (
    generate_payroll,
    finalize_payroll,
    recompute_payroll_record,
    update_payroll_record_deductions,
    bulk_assign_salary,
    bulk_close_salary_assignments,
)

from .payments import (
    record_payment,
    update_payment_status,
    bulk_record_payment_for_run,
)


__all__ = [
    # Constants
    "ZERO",
    "ONE",
    "TWOPLACES",
    "HUNDRED",
    "PAYROLL_ELIGIBLE_STATUSES",
    "STATUTORY_COMPONENT_ROLES",

    # Lookups
    "get_statutory_rate",
    "get_pt_slab_amount",

    # Cycle
    "compute_cycle_period",

    # Payslip
    "compute_payslip_data",

    # Generation & finalization
    "generate_payroll",
    "finalize_payroll",

    # Recompute
    "recompute_payroll_record",

    # Manual deductions
    "update_payroll_record_deductions",

    # Assignment
    "bulk_assign_salary",
    "bulk_close_salary_assignments",

    # Payments
    "record_payment",
    "update_payment_status",
    "bulk_record_payment_for_run",
]
