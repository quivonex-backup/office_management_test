# Run from your backend folder:
#     python manage.py shell < payroll_check.py
#
# Safe: every scenario runs inside a transaction that is ALWAYS rolled back,
# so nothing is saved. Change APP below if your app path is different.

from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction

from app.payroll.models import PayrollSettings, EmployeeSalaryAssignment
from app.payroll.services import (
    compute_payslip_data, bulk_assign_salary, compute_cycle_period,
)
from app.attendance.models import EmployeeShiftAssignment


class _Rollback(Exception):
    pass


def sandbox(fn):
    try:
        with transaction.atomic():
            fn()
            raise _Rollback()
    except _Rollback:
        pass


def line(ok, text):
    print(("   PASS  " if ok else "   FAIL  ") + text)


s = PayrollSettings.objects.first()
org = s.organization
cd = s.cycle_start_day
a = (EmployeeSalaryAssignment.objects
     .filter(organization=org, employee__is_active=True)
     .select_related("employee", "salary_structure").first())
emp = a.employee
ps, pe = compute_cycle_period(cd, reference=a.effective_from)
period_days = (pe - ps).days + 1
join = ps + timedelta(days=14)

print("=" * 70)
print(f"Org {org.id} | cycle_start_day={cd} | test employee {emp.employee_code}")
print(f"Test period {ps} to {pe} ({period_days} days); fake joining date {join}")
print(f"Assignment used: {a.effective_from} to {a.effective_to or 'open'}")
print("=" * 70)

# ---------------------------------------------------------------- 1
print("\n[1] Existing assignments NOT starting on a cycle start date")
bad = []
for x in EmployeeSalaryAssignment.objects.filter(organization=org).select_related("employee"):
    cs, _ = compute_cycle_period(cd, reference=x.effective_from)
    if x.effective_from != cs:
        bad.append(x)
        print(f"   {x.employee.employee_code}  from {x.effective_from} to {x.effective_to or 'open'}"
              f"  (cycle starts {cs})")

line(not bad, f"{len(bad)} misaligned assignment(s). Expected: 0")

# ---------------------------------------------------------------- 2
print("\n[2] Joining mid-period: LOP for the days before joining")


def joining(basis):
    def run():
        s.salary_basis = basis
        s.save()
        emp.joining_date = join
        emp.save()
        d = compute_payslip_data(emp, org, ps, pe)
        b = d["breakdown"]
        lop = next((li["amount"] for li in d["line_items"] if li["component_type"] == "LOP"), 0)
        print(f"   basis={basis}: not_employed_days={b['not_employed_days']} "
              f"base_days={b['base_days']} eff_absent_equiv={b['effective_absent_equivalent']} "
              f"LOP={lop} net={d['net']}")
        if basis == "WORKING_DAYS":
            print("   breakdown:", {k: str(v) for k, v in b.items()})
            print("   present/half/absent/leave:", d.get("present_days"), d.get("half_days"),
                  d.get("absent_days"), d.get("unpaid_leave_days"))
            print("   shifts:", list(EmployeeShiftAssignment.objects.filter(employee=emp)
                  .values_list("effective_from", "effective_to")))
        if basis != "WORKING_DAYS":
            base = Decimal(b["base_days"])
            absence = (d["absent_days"] * s.absent_deduction_multiplier
                       + d["half_days"] * s.half_day_deduction_multiplier
                       + d["unpaid_leave_days"] * s.unpaid_leave_multiplier)
            expected = absence + base * Decimal(14) / Decimal(period_days)
            got = Decimal(b["effective_absent_equivalent"])
            line(abs(got - expected) < Decimal("0.01"),
                 f"eff_absent_equiv {got} vs expected {expected.quantize(Decimal('0.01'))}")
        line(b["not_employed_days"] in ("14", "14.00"), "not_employed_days is 14")
    return run


for basis in ("FIXED_30", "CALENDAR_DAYS", "WORKING_DAYS"):
    try:
        sandbox(joining(basis))
    except Exception as exc:
        print(f"   basis={basis}: ERROR {exc}")

# ---------------------------------------------------------------- 3
print("\n[3] Assignment starts AFTER period start -> review warning expected")


def partial():
    a.effective_from = ps + timedelta(days=10)
    a.save()
    d = compute_payslip_data(emp, org, ps, pe)
    hit = [w for w in d["warnings"] if "not the whole period" in w]
    line(bool(hit) and d["requires_review"], "warning present and requires_review is True")
    if hit:
        print("   ", hit[0])


try:
    sandbox(partial)
except Exception as exc:
    print("   ERROR", exc)

# ---------------------------------------------------------------- 4
print("\n[4] WORKING_DAYS + joined mid-period + NO shift at all -> safety warning expected")


def noshift():
    s.salary_basis = "WORKING_DAYS"
    s.save()
    emp.joining_date = join
    emp.save()
    EmployeeShiftAssignment.objects.filter(employee=emp).delete()
    d = compute_payslip_data(emp, org, ps, pe)
    hit = [w for w in d["warnings"] if "no scheduled working days were found" in w]
    line(bool(hit), "safety warning present")
    if hit:
        print("   ", hit[0])


try:
    sandbox(noshift)
except Exception as exc:
    print("   ERROR", exc)

# ---------------------------------------------------------------- 5
print("\n[5] bulk_assign_salary cycle-boundary rule (far-future dates, rolled back)")
fs, fe = compute_cycle_period(cd, reference=date(2035, 6, 20))


def bulk_mid():
    EmployeeSalaryAssignment.objects.filter(
        employee=emp, effective_to__isnull=True).update(effective_to=date(2030, 1, 1))
    try:
        bulk_assign_salary(org, [emp.id], a.salary_structure_id,
                           effective_from=fs + timedelta(days=1), effective_to=fe)
        line(False, "mid-cycle date was ACCEPTED (expected a ValueError)")
    except ValueError as exc:
        line("cycle boundary" in str(exc), f"mid-cycle rejected: {exc}")


def bulk_ok():
    EmployeeSalaryAssignment.objects.filter(
        employee=emp, effective_to__isnull=True).update(effective_to=date(2030, 1, 1))
    try:
        made = bulk_assign_salary(org, [emp.id], a.salary_structure_id,
                                  effective_from=fs, effective_to=fe)
        line(len(made) == 1, f"cycle-start date {fs} accepted, {len(made)} created (rolled back)")
    except ValueError as exc:
        line(False, f"cycle-start date was rejected: {exc}")


for fn in (bulk_mid, bulk_ok):
    try:
        sandbox(fn)
    except Exception as exc:
        print("   ERROR", exc)

print("\nDone. Nothing was saved.")