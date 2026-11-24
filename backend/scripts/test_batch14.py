"""
Batch 14 checks: payroll runs/reopen + payments/void; attendance
corrections/missed-day (+ paired review) and corrections/cancel.

Run after migrate; any database; everything is rolled back:
    python manage.py shell -c "exec(open('scripts/test_batch14.py').read())"
"""
import sys
import traceback
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest import mock

from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from app.accounts.models import AccessRole, Organization, OrganizationMembership, Role, User
from app.accounts.services import seed_organization_defaults
from app.attendance.models import AttendanceCorrection, AttendanceRecord, AttendanceSettings
from app.employees.models import Employee
from app.payroll.models import (
    EmployeeSalaryAssignment, PayrollPayment, PayrollRecord, PayrollRun, PayrollSettings, SalaryComponent,
    SalaryStructure, SalaryStructureComponent,
)

RESULTS = []
D = Decimal
P_START, P_END = date(2026, 10, 1), date(2026, 10, 31)


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition)))
    print(("PASS " if condition else "FAIL ") + name + ("" if condition else f"  -> {detail}"))


class Rollback(Exception):
    pass


def client_for(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def post(c, url, data=None):
    r = c.post("/" + url, data or {}, format="json")
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.content[:200]}


def counts(days=31):
    Z = D("0")
    return {
        "counts": {"working_days": D(days), "present_days": D(days), "half_days": Z, "absent_days": Z,
                   "paid_leave_days": Z, "unpaid_leave_days": Z, "holiday_days": Z, "weekly_off_days": Z,
                   "not_employed_days": Z, "not_employed_working_days": Z},
        "overtime_minutes": 0, "late_minutes": 0, "warnings": [], "notes": [], "requires_review": False,
        "sources": {},
    }


def iso(day, hh, mm=0):
    return timezone.make_aware(datetime.combine(day, time(hh, mm))).isoformat()


def run():
    admin_role, _ = Role.objects.get_or_create(name="Admin", defaults={"is_active": True})
    emp_role, _ = Role.objects.get_or_create(name="Employee", defaults={"is_active": True})
    n = [0]

    def user(name, role=emp_role):
        n[0] += 1
        return User.objects.create(username=f"b14_{name}", email=f"b14_{name}@x.test", mobile=f"14000000{n[0]:02d}",
                                   role=role, first_name=name.title())

    owner = user("owner", admin_role)
    org = Organization.objects.create(organization_name="B14 Org", owner=owner, email="hr@b14.test")
    OrganizationMembership.objects.create(organization=org, user=owner, is_active=True)
    seed_organization_defaults(org)
    roles = {r.name: r for r in AccessRole.objects.filter(organization=org)}

    def employee(name, role=None, **kw):
        u = user(name)
        OrganizationMembership.objects.create(organization=org, user=u, is_active=True)
        return Employee.objects.create(organization=org, first_name=name.title(), last_name="T",
                                       employee_code=f"B14-{name}", user=u, access_role=role,
                                       employment_status="ACTIVE", joining_date=date(2025, 1, 1), **kw)

    hr = employee("hr", roles["HR Manager"])
    pay = employee("pay", roles["Payroll Manager"])
    mgr = employee("mgr", roles["Department Manager"])
    dev = employee("dev", reports_to=mgr)
    other = employee("other")
    C = {k: client_for(v.user) for k, v in dict(hr=hr, pay=pay, mgr=mgr, dev=dev, other=other).items()}
    C["owner"] = client_for(owner)

    # ================= PAYROLL: generate + finalize a run
    PayrollSettings.objects.create(organization=org, cycle_start_day=1, payslip_mode="SIMPLE",
                                   salary_basis="CALENDAR_DAYS", standard_work_hours_per_day=D("8"))
    basic = SalaryComponent.objects.create(organization=org, name="Basic", code="BASIC", component_type="EARNING",
                                           calculation_type="FIXED", component_role="BASIC")
    st = SalaryStructure.objects.create(organization=org, name="Flat", code="FLAT")
    SalaryStructureComponent.objects.create(salary_structure=st, salary_component=basic, amount=D("31000"))
    for e in Employee.objects.filter(organization=org):
        EmployeeSalaryAssignment.objects.create(organization=org, employee=e, salary_structure=st,
                                                effective_from=P_START)

    with mock.patch("app.payroll.services.computation.compute_attendance_counts", return_value=counts()):
        s, b = post(C["owner"], "payroll/runs/create/", {"period_start": str(P_START), "period_end": str(P_END)})
        run_id = b["data"]["id"]
        s, b = post(C["owner"], "payroll/runs/generate/", {"payroll_run_id": run_id})
        check("setup: run generated", s == 200, b)
        s, b = post(C["owner"], "payroll/runs/finalize/", {"payroll_run_id": run_id})
        check("setup: run finalized", s == 200, b)

    rec = PayrollRecord.objects.filter(payroll_run_id=run_id, employee=dev).first()

    s, b = post(C["dev"], "payroll/runs/reopen/", {"payroll_run_id": run_id, "reason": "x"})
    check("reopen needs payroll.finalize -> 403", s == 403, s)
    s, b = post(C["owner"], "payroll/runs/reopen/", {"payroll_run_id": run_id})
    check("reopen: reason required", s == 400 and "reason" in b["message"], b)

    s, b = post(C["owner"], "payroll/payments/record/", {"payroll_record_id": rec.id, "amount": "1000.00",
                                                       "payment_date": "2026-11-05", "payment_mode": "CASH",
                                                       "transaction_reference": "WRONG"})
    check("setup: payment recorded", s in (200, 201), b)
    pay_id = PayrollPayment.objects.get(payroll_record=rec).id
    s, b = post(C["owner"], "payroll/runs/reopen/", {"payroll_run_id": run_id, "reason": "Wrong TDS"})
    check("reopen blocked while payments exist (lists ids)", s == 400 and pay_id in b["errors"]["payment_ids"], b)

    s, b = post(C["dev"], "payroll/payments/void/", {"payment_id": pay_id, "reason": "x"})
    check("void needs payroll.finalize -> 403", s == 403, s)
    s, b = post(C["owner"], "payroll/payments/void/", {"payment_id": pay_id})
    check("void: reason required", s == 400, b)
    s, b = post(C["owner"], "payroll/payments/void/", {"payment_id": pay_id, "reason": "Wrong reference"})
    rec.refresh_from_db()
    check("void -> payment gone, record UNPAID, paid 0",
          s == 200 and not PayrollPayment.objects.filter(pk=pay_id).exists() and rec.payment_status == "UNPAID"
          and rec.paid_amount == D("0") and b["data"]["payment_status"] == "UNPAID", b)
    s, b = post(C["owner"], "payroll/payments/void/", {"payment_id": pay_id, "reason": "again"})
    check("void twice -> 404", s == 404, b)
    from app.audit.models import ActivityLog
    check("void kept in activity log with old data",
          ActivityLog.objects.filter(object_type="PayrollPayment", object_id=str(pay_id), action="DELETE").exists()
          or ActivityLog.objects.filter(object_type="PayrollPayment", object_id=pay_id, action="DELETE").exists())

    s, b = post(C["dev"], "payroll/my/payslips/", {})
    check("employee sees payslip while FINALIZED", s == 200 and len(b["data"]) >= 1, b)
    s, b = post(C["pay"], "payroll/runs/reopen/", {"payroll_run_id": run_id, "reason": "Wrong TDS for dev"})
    run_obj = PayrollRun.objects.get(pk=run_id)
    check("reopen -> GENERATED, finalized fields cleared (Payroll Manager)",
          s == 200 and run_obj.status == "GENERATED" and run_obj.finalized_at is None
          and b["data"]["status"] == "GENERATED", b)
    s, b = post(C["dev"], "payroll/my/payslips/", {})
    check("payslip hidden from employee while reopened", s == 200 and len(b["data"]) == 0, b)
    s, b = post(C["owner"], "payroll/runs/reopen/", {"payroll_run_id": run_id, "reason": "again"})
    check("reopen a GENERATED run -> 400", s == 400, b)
    s, b = post(C["owner"], "payroll/records/update-deductions/", {"payroll_record_id": rec.id, "tds": "500.00"})
    rec.refresh_from_db()
    check("deductions editable again after reopen", s == 200 and rec.net == D("30500.00"), (s, b, rec.net))
    s, b = post(C["owner"], "payroll/runs/finalize/", {"payroll_run_id": run_id})
    check("finalize again", s == 200 and PayrollRun.objects.get(pk=run_id).status == "FINALIZED", b)
    s, b = post(C["owner"], "payroll/payments/record/", {"payroll_record_id": rec.id, "amount": "30500.00",
                                                       "payment_date": "2026-11-05", "payment_mode": "CASH"})
    rec.refresh_from_db()
    check("pay corrected net -> PAID", s in (200, 201) and rec.payment_status == "PAID", b)

    # ================= ATTENDANCE: missed day
    AttendanceSettings.objects.update_or_create(organization=org, defaults=dict(
        default_start_time=time(9, 0), default_end_time=time(18, 0)))
    today = timezone.localdate()
    d1, d2, d3 = today - timedelta(days=3), today - timedelta(days=4), today - timedelta(days=5)

    s, b = post(C["dev"], "attendance/corrections/missed-day/", {"work_date": str(d1)})
    check("missing fields -> 400 with errors", s == 400 and {"check_in", "check_out", "reason"} <= set(b["errors"]), b)
    s, b = post(C["dev"], "attendance/corrections/missed-day/", {
        "work_date": str(today + timedelta(days=1)), "check_in": iso(today + timedelta(days=1), 9),
        "check_out": iso(today + timedelta(days=1), 18), "reason": "x"})
    check("future day -> 400", s == 400, b)
    s, b = post(C["dev"], "attendance/corrections/missed-day/", {
        "work_date": str(d1), "check_in": iso(d1, 18), "check_out": iso(d1, 9), "reason": "x"})
    check("check_out before check_in -> 400", s == 400, b)
    s, b = post(C["dev"], "attendance/corrections/missed-day/", {
        "work_date": str(d1), "check_in": iso(d2, 9), "check_out": iso(d1, 18), "reason": "x"})
    check("check_in not on work_date -> 400", s == 400, b)
    s, b = post(C["dev"], "attendance/corrections/missed-day/", {
        "work_date": str(d1), "check_in": iso(d1, 9, 5), "check_out": iso(d1, 18, 10), "reason": "Forgot phone"})
    data = b.get("data") or {}
    check("missed day -> 201, two PENDING corrections", s == 201 and [c["field_name"] for c in data["corrections"]]
          == ["CHECK_IN", "CHECK_OUT"] and all(c["status"] == "PENDING" for c in data["corrections"]), b)
    ci_id, co_id = data["corrections"][0]["id"], data["corrections"][1]["id"]
    rec1 = AttendanceRecord.objects.get(employee=dev, work_date=d1)
    check("record created INCOMPLETE without times", rec1.status == "INCOMPLETE" and not rec1.check_in, rec1.status)
    s, b = post(C["dev"], "attendance/corrections/missed-day/", {
        "work_date": str(d1), "check_in": iso(d1, 9), "check_out": iso(d1, 18), "reason": "again"})
    check("second request same day -> 400 pending", s == 400 and "pending" in b["message"], b)
    s, b = post(C["dev"], "attendance/corrections/missed-day/", {
        "employee_id": other.id, "work_date": str(d1), "check_in": iso(d1, 9), "check_out": iso(d1, 18),
        "reason": "x"})
    check("for someone else without attendance.correct -> 403", s == 403, b)

    s, b = post(C["mgr"], "attendance/corrections/review/", {"correction_id": co_id, "approve": True})
    rec1.refresh_from_db()
    check("manager approves CHECK_OUT line -> pair applied (check-in first), PRESENT",
          s == 200 and b["data"].get("paired_correction_id") == ci_id and rec1.check_in and rec1.check_out
          and rec1.status == "PRESENT"
          and set(AttendanceCorrection.objects.filter(id__in=[ci_id, co_id]).values_list("status", flat=True))
          == {"APPLIED"}, (b, rec1.status))
    s, b = post(C["dev"], "attendance/corrections/missed-day/", {
        "work_date": str(d1), "check_in": iso(d1, 9), "check_out": iso(d1, 18), "reason": "x"})
    check("day now has times -> 400 use corrections/create", s == 400 and "corrections/create" in b["message"], b)

    # reject pair -> ABSENT
    s, b = post(C["dev"], "attendance/corrections/missed-day/", {
        "work_date": str(d2), "check_in": iso(d2, 9), "check_out": iso(d2, 18), "reason": "x"})
    ci2 = b["data"]["corrections"][0]["id"]
    s, b = post(C["mgr"], "attendance/corrections/review/", {"correction_id": ci2, "approve": False,
                                                           "review_note": "Not in office"})
    rec2 = AttendanceRecord.objects.get(employee=dev, work_date=d2)
    check("reject -> both REJECTED, day ABSENT", s == 200 and rec2.status == "ABSENT"
          and set(rec2.corrections.values_list("status", flat=True)) == {"REJECTED"}, (b, rec2.status))

    # HR for someone else, existing ABSENT record reused
    AttendanceRecord.objects.create(organization=org, employee=other, work_date=d3, status="ABSENT")
    s, b = post(C["hr"], "attendance/corrections/missed-day/", {
        "employee_id": other.id, "work_date": str(d3), "check_in": iso(d3, 9), "check_out": iso(d3, 13),
        "reason": "Client visit"})
    check("HR (attendance.correct) requests for another employee, ABSENT record reused",
          s == 201 and AttendanceRecord.objects.filter(employee=other, work_date=d3).count() == 1, b)

    # ================= CANCEL (withdraw)
    s, b = post(C["dev"], "attendance/corrections/missed-day/", {
        "work_date": str(d3), "check_in": iso(d3, 9), "check_out": iso(d3, 18), "reason": "x"})
    w_ids = [c["id"] for c in b["data"]["corrections"]]
    s, b = post(C["other"], "attendance/corrections/cancel/", {"correction_id": w_ids[0]})
    check("someone else cannot withdraw -> 403", s == 403, b)
    s, b = post(C["dev"], "attendance/corrections/cancel/", {"correction_id": w_ids[1]})
    check("withdraw missed day -> both removed + empty record removed",
          s == 200 and sorted(b["data"]["withdrawn_correction_ids"]) == sorted(w_ids)
          and b["data"]["attendance_record_removed"]
          and not AttendanceRecord.objects.filter(employee=dev, work_date=d3).exists(), b)
    s, b = post(C["dev"], "attendance/corrections/cancel/", {"correction_id": ci_id})
    check("withdraw an APPLIED one -> 400", s == 400, b)

    # normal single correction withdraw
    s, b = post(C["dev"], "attendance/corrections/create/", {"attendance": rec1.id, "field_name": "CHECK_OUT",
                                                            "new_value": iso(d1, 19), "reason": "Left later"})
    single = b.get("data", {}).get("id")
    s, b = post(C["dev"], "attendance/corrections/cancel/", {"correction_id": single})
    check("withdraw a normal correction (record kept)",
          s == 200 and b["data"]["withdrawn_correction_ids"] == [single] and not b["data"]["attendance_record_removed"]
          and AttendanceRecord.objects.filter(pk=rec1.pk).exists(), b)
    s, b = post(C["dev"], "attendance/corrections/cancel/", {"correction_id": 999999})
    check("unknown correction -> 404", s == 404, b)

    # normal correction still reviewed alone
    s, b = post(C["dev"], "attendance/corrections/create/", {"attendance": rec1.id, "field_name": "CHECK_OUT",
                                                            "new_value": iso(d1, 19), "reason": "Left later"})
    s, b = post(C["mgr"], "attendance/corrections/review/", {"correction_id": b["data"]["id"], "approve": True})
    check("normal correction review unchanged (no paired id)", s == 200 and "paired_correction_id" not in b["data"], b)


try:
    with transaction.atomic():
        run()
        raise Rollback()
except Rollback:
    pass
except Exception:
    traceback.print_exc()
    RESULTS.append(("crashed", False))

passed = sum(1 for _, ok in RESULTS if ok)
print(f"\nBatch 14: {passed}/{len(RESULTS)} passed (all changes rolled back)")
if passed != len(RESULTS):
    sys.exit(1)
