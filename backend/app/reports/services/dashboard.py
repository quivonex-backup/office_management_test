"""
Dashboard widgets. Each widget declares the codes that unlock it; the
dashboard returns only the widgets the caller may see. "My" widgets need an
employee profile; celebrations / holidays / announcements are for everyone.
"""
import logging
from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone

from common.permissions import get_user_employee, has_perm

from .common import (
    ZERO, chart, day_end_exclusive, day_start, days_between, emp_name, dept_name, fmt_time,
    minutes_to_hours, month_bounds, num, org_features,
)

logger = logging.getLogger(__name__)

WORKED = ("PRESENT", "HALF_DAY", "INCOMPLETE", "PENDING_REVIEW")


class Ctx:
    def __init__(self, request, organization, today, month_first, month_last):
        self.request = request
        self.org = organization
        self.today = today
        self.month_first = month_first
        self.month_last = month_last
        self.employee = get_user_employee(request.user, organization)
        self._features = None

    def can(self, *codes):
        return any(has_perm(self.request, self.org, c) for c in codes)

    @property
    def features(self):
        if self._features is None:
            self._features = org_features(self.org)
        return self._features


def _photo(emp):
    try:
        return emp.profile_photo.url if emp.profile_photo else None
    except Exception:
        return None


def _person(emp):
    return {"employee_id": emp.id, "employee_code": emp.employee_code, "name": emp_name(emp),
            "department": dept_name(emp),
            "designation": emp.designation_ref.name if getattr(emp, "designation_ref", None) else (emp.designation or None),
            "photo": _photo(emp)}


# =========================================================
# EVERYONE
# =========================================================
def w_celebrations(ctx):
    from app.employees.models import Employee

    today = ctx.today
    days = [(today.month, today.day)]
    # 29 Feb birthdays / joinings show on 28 Feb in non-leap years
    if today.month == 2 and today.day == 28:
        import calendar
        if not calendar.isleap(today.year):
            days.append((2, 29))
    cond_b = Q()
    cond_a = Q()
    for m, d in days:
        cond_b |= Q(date_of_birth__month=m, date_of_birth__day=d)
        cond_a |= Q(joining_date__month=m, joining_date__day=d)
    base = Employee.objects.filter(organization=ctx.org, is_active=True).select_related("department_ref", "designation_ref")
    birthdays = [_person(e) for e in base.filter(date_of_birth__isnull=False).filter(cond_b).order_by("first_name")]
    anniversaries = []
    for e in base.filter(joining_date__isnull=False, joining_date__year__lt=today.year).filter(cond_a).order_by("joining_date"):
        item = _person(e)
        item["years"] = today.year - e.joining_date.year
        anniversaries.append(item)
    return {"date": str(today), "birthdays": birthdays, "anniversaries": anniversaries}


def w_upcoming_holidays(ctx):
    from app.calendar_app.models import CalendarHoliday

    qs = CalendarHoliday.objects.filter(organization=ctx.org, is_active=True, date__gte=ctx.today).order_by("date")[:5]
    return [{"date": str(h.date), "name": h.name, "holiday_type": h.holiday_type,
             "is_optional": h.is_optional} for h in qs]


def w_announcements(ctx):
    from app.communications.models import Announcement

    now = timezone.now()
    qs = (Announcement.objects.filter(organization=ctx.org, is_active=True)
          .filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now))
          .order_by("-is_pinned", "-created_at")[:5])
    return [{"id": a.id, "title": a.title, "priority": a.priority, "is_pinned": a.is_pinned,
             "created_at": timezone.localtime(a.created_at).isoformat()} for a in qs]


# =========================================================
# MY (needs an employee profile)
# =========================================================
def w_my_today(ctx):
    from app.attendance.models import AttendanceRecord
    from app.attendance.services import get_employee_shift
    from app.calendar_app.services import get_calendar_day

    emp = ctx.employee
    shift = get_employee_shift(emp, ctx.org, ctx.today)
    try:
        day_type = get_calendar_day(organization=ctx.org, target_date=ctx.today, shift=shift).get("day_type")
    except Exception:
        day_type = None
    rec = AttendanceRecord.objects.filter(employee=emp, work_date=ctx.today).first()
    return {
        "date": str(ctx.today),
        "day_type": day_type,
        "shift": ({"name": shift.name, "start": shift.start_time.strftime("%H:%M"),
                   "end": shift.end_time.strftime("%H:%M")} if shift else None),
        "check_in": fmt_time(rec.check_in) if rec else None,
        "check_out": fmt_time(rec.check_out) if rec else None,
        "status": rec.status if rec else "NOT_PUNCHED",
        "late_minutes": rec.late_minutes if rec else 0,
        "worked_hours": minutes_to_hours(rec.net_work_minutes) if rec else 0,
        "remote": bool(getattr(emp, "attendance_location_exempt", False)),
    }


def w_my_month(ctx):
    from app.attendance.models import AttendanceRecord

    end = min(ctx.month_last, ctx.today)
    recs = list(AttendanceRecord.objects.filter(employee=ctx.employee, work_date__gte=ctx.month_first,
                                                work_date__lte=end))
    by_day = {r.work_date: r for r in recs}
    counts = {"present": 0, "half_days": 0, "absent": 0, "on_leave": 0}
    for r in recs:
        if r.status == "PRESENT":
            counts["present"] += 1
        elif r.status == "HALF_DAY":
            counts["half_days"] += 1
        elif r.status == "ABSENT":
            counts["absent"] += 1
        elif r.status == "ON_LEAVE":
            counts["on_leave"] += 1
    labels, hours = [], []
    for d in days_between(ctx.month_first, end):
        labels.append(d.strftime("%d %b"))
        r = by_day.get(d)
        hours.append(minutes_to_hours(r.net_work_minutes) if r and r.check_out else 0)
    return {
        "month": ctx.month_first.strftime("%Y-%m"),
        **counts,
        "late_days": sum(1 for r in recs if r.late_minutes),
        "late_minutes": sum(r.late_minutes for r in recs),
        "overtime_hours": minutes_to_hours(sum(r.overtime_minutes for r in recs)),
        "chart": chart("bar", labels, [{"name": "Worked hours", "data": hours}]),
    }


def w_my_leave_balance(ctx):
    from app.leave.models import EmployeeLeaveBalance

    qs = (EmployeeLeaveBalance.objects.filter(employee=ctx.employee, leave_year=ctx.today.year,
                                              leave_type__is_active=True)
          .select_related("leave_type").order_by("leave_type__name"))
    return [{"leave_type": b.leave_type.name, "code": b.leave_type.code,
             "allocated": num(b.opening_balance + b.allocated_days), "used": num(b.used_days),
             "pending": num(b.pending_days), "available": num(b.available)} for b in qs]


def w_my_recent_leaves(ctx):
    from app.leave.models import LeaveApplication

    qs = LeaveApplication.objects.filter(employee=ctx.employee).select_related("leave_type").order_by("-created_at")[:5]
    return [{"id": a.id, "leave_type": a.leave_type.name, "from": str(a.start_date), "to": str(a.end_date),
             "days": num(a.total_days), "status": a.status} for a in qs]


def w_my_work(ctx):
    from app.assets.models import Asset
    from app.helpdesk.models import Ticket
    from app.projects.models import Task

    emp = ctx.employee
    soon = ctx.today + timedelta(days=7)
    tasks = (Task.objects.filter(organization=ctx.org, assigned_to=emp, is_active=True, due_date__isnull=False,
                                 due_date__lte=soon).exclude(status="DONE")
             .select_related("project").order_by("due_date")[:5])
    return {
        "open_tickets": Ticket.objects.filter(organization=ctx.org, raised_by=emp, is_active=True)
        .exclude(status__in=("RESOLVED", "CLOSED")).count(),
        "assigned_tickets": Ticket.objects.filter(organization=ctx.org, assigned_to=emp, is_active=True)
        .exclude(status__in=("RESOLVED", "CLOSED")).count(),
        "tasks_due": [{"id": t.id, "title": t.title, "project": t.project.project_name, "due_date": str(t.due_date),
                       "status": t.status, "overdue": t.due_date < ctx.today} for t in tasks],
        "assets_held": Asset.objects.filter(organization=ctx.org, current_holder=emp, status="ASSIGNED",
                                            is_active=True).count(),
    }


# =========================================================
# TEAM / APPROVALS
# =========================================================
def _team_ids(ctx):
    from common.services import get_team_employee_ids

    return [i for i in get_team_employee_ids(ctx.employee) if i != ctx.employee.id]


def _today_counts(ctx, employee_ids=None):
    from app.attendance.models import AttendanceRecord
    from app.employees.models import Employee
    from app.leave.models import LeaveApplication

    emps = Employee.objects.filter(organization=ctx.org, is_active=True)
    if employee_ids is not None:
        emps = emps.filter(id__in=employee_ids)
    total = emps.count()
    recs = AttendanceRecord.objects.filter(organization=ctx.org, work_date=ctx.today, employee__in=emps)
    on_leave_ids = set(LeaveApplication.objects.filter(
        organization=ctx.org, status="APPROVED", start_date__lte=ctx.today, end_date__gte=ctx.today,
        employee__in=emps).values_list("employee_id", flat=True))
    on_leave_ids |= set(recs.filter(status="ON_LEAVE").values_list("employee_id", flat=True))
    punched = set(recs.filter(check_in__isnull=False).values_list("employee_id", flat=True))
    off = set(recs.filter(status__in=("WEEKLY_OFF", "HOLIDAY")).values_list("employee_id", flat=True))
    absent = set(recs.filter(status="ABSENT").values_list("employee_id", flat=True))
    return {
        "total": total,
        "present": len(punched),
        "late": recs.filter(check_in__isnull=False, late_minutes__gt=0).count(),
        "on_leave": len(on_leave_ids - punched),
        "absent": len(absent - punched - on_leave_ids),
        "day_off": len(off - punched),
        "not_punched": max(total - len(punched | on_leave_ids | absent | off), 0),
    }


def w_team_today(ctx):
    ids = _team_ids(ctx)
    return {"team_size": len(ids), **_today_counts(ctx, ids)}


def w_pending_approvals(ctx):
    from app.attendance.models import AttendanceCorrection
    from app.leave.models import LeaveApplication

    out = {}
    if ctx.can("leave.approve"):
        qs = LeaveApplication.objects.filter(organization=ctx.org, status="PENDING").select_related("employee", "leave_type")
        if not ctx.can("leave.view_all"):
            qs = qs.filter(employee_id__in=_team_ids(ctx) if ctx.employee else [])
        if ctx.employee:
            qs = qs.exclude(employee=ctx.employee)
        out["leave"] = {"count": qs.count(), "latest": [
            {"id": a.id, "employee": emp_name(a.employee), "leave_type": a.leave_type.name,
             "from": str(a.start_date), "to": str(a.end_date), "days": num(a.total_days)}
            for a in qs.order_by("-created_at")[:5]]}
    if ctx.can("attendance.approve_correction"):
        qs = AttendanceCorrection.objects.filter(attendance__organization=ctx.org, status="PENDING") \
            .select_related("attendance__employee")
        if not ctx.can("attendance.view_all"):
            qs = qs.filter(attendance__employee_id__in=_team_ids(ctx) if ctx.employee else [])
        if ctx.employee:
            qs = qs.exclude(attendance__employee=ctx.employee)
        out["attendance_corrections"] = {"count": qs.count(), "latest": [
            {"id": c.id, "employee": emp_name(c.attendance.employee), "work_date": str(c.attendance.work_date),
             "field": c.field_name, "reason": c.reason[:120]} for c in qs.order_by("-id")[:5]]}
    return out


# =========================================================
# ORGANIZATION
# =========================================================
def w_org_today(ctx):
    from app.attendance.models import AttendancePunch

    punches = (AttendancePunch.objects.filter(attendance__organization=ctx.org,
                                              punched_at__gte=day_start(ctx.today),
                                              punched_at__lt=day_end_exclusive(ctx.today))
               .select_related("attendance__employee").order_by("-punched_at")[:5])
    return {**_today_counts(ctx), "recent_punches": [
        {"employee": emp_name(p.attendance.employee), "employee_code": p.attendance.employee.employee_code,
         "punch_type": p.punch_type, "time": fmt_time(p.punched_at)} for p in punches]}


def w_attendance_trend(ctx):
    from app.attendance.models import AttendanceRecord

    start = ctx.today - timedelta(days=29)
    rows = (AttendanceRecord.objects.filter(organization=ctx.org, work_date__gte=start, work_date__lte=ctx.today)
            .values("work_date").annotate(
                present=Count("id", filter=Q(status__in=WORKED)),
                absent=Count("id", filter=Q(status="ABSENT")),
                on_leave=Count("id", filter=Q(status="ON_LEAVE")),
                late=Count("id", filter=Q(late_minutes__gt=0)),
            ))
    by_day = {r["work_date"]: r for r in rows}
    labels, series = [], {"Present": [], "Absent": [], "On leave": [], "Late": []}
    for d in days_between(start, ctx.today):
        labels.append(d.strftime("%d %b"))
        r = by_day.get(d, {})
        series["Present"].append(r.get("present", 0))
        series["Absent"].append(r.get("absent", 0))
        series["On leave"].append(r.get("on_leave", 0))
        series["Late"].append(r.get("late", 0))
    return chart("line", labels, [{"name": k, "data": v} for k, v in series.items()])


def w_recent_leave_requests(ctx):
    from app.leave.models import LeaveApplication

    qs = LeaveApplication.objects.filter(organization=ctx.org).select_related("employee", "leave_type")
    return {"pending": qs.filter(status="PENDING").count(), "latest": [
        {"id": a.id, "employee": emp_name(a.employee), "leave_type": a.leave_type.name,
         "from": str(a.start_date), "to": str(a.end_date), "days": num(a.total_days), "status": a.status}
        for a in qs.order_by("-created_at")[:5]]}


def w_headcount(ctx):
    from app.employees.models import Employee

    active = Employee.objects.filter(organization=ctx.org, is_active=True)
    out = {
        "total": active.count(),
        "joined_this_month": Employee.objects.filter(organization=ctx.org, joining_date__gte=ctx.month_first,
                                                     joining_date__lte=ctx.month_last).count(),
        "exited_this_month": Employee.objects.filter(organization=ctx.org, is_active=False,
                                                     resignation_date__gte=ctx.month_first,
                                                     resignation_date__lte=ctx.month_last).count(),
        "remote": active.filter(attendance_location_exempt=True).count(),
    }
    if ctx.features["has_departments"]:
        rows = active.values("department_ref__name").annotate(n=Count("id")).order_by("-n")
        out["by_department"] = chart("bar", [r["department_ref__name"] or "Not set" for r in rows],
                                     [{"name": "Employees", "data": [r["n"] for r in rows]}])
    if ctx.features["has_branches"]:
        rows = active.values("branch__name").annotate(n=Count("id")).order_by("-n")
        out["by_branch"] = chart("bar", [r["branch__name"] or "Not set" for r in rows],
                                 [{"name": "Employees", "data": [r["n"] for r in rows]}])
    return out


def w_payroll_summary(ctx):
    from app.payroll.models import PayrollRun

    runs = list(PayrollRun.objects.filter(organization=ctx.org).order_by("-period_end")[:6])
    if not runs:
        return {"last_run": None, "trend": None}
    last = runs[0]
    trend_runs = list(reversed(runs))
    return {
        "last_run": {"id": last.id, "period_start": str(last.period_start), "period_end": str(last.period_end),
                     "status": last.status, "employees": last.total_employees,
                     "gross": num(last.total_gross), "deductions": num(last.total_deductions),
                     "net": num(last.total_net)},
        "trend": chart("bar", [r.period_end.strftime("%b %Y") for r in trend_runs], [
            {"name": "Gross", "data": [num(r.total_gross) for r in trend_runs]},
            {"name": "Deductions", "data": [num(r.total_deductions) for r in trend_runs]},
            {"name": "Net", "data": [num(r.total_net) for r in trend_runs]},
        ]),
    }


def w_recruitment_pipeline(ctx):
    from app.recruitment.models import Applicant, ApplicantOffer

    from .recruitment import visible_applicants

    qs = visible_applicants(ctx.request, ctx.org).exclude(stage__in=("COMPLETED", "CLOSED"))
    rows = qs.values("stage").annotate(n=Count("id"))
    stages = dict((r["stage"], r["n"]) for r in rows)
    labels = [label for code, label in Applicant.STAGE_CHOICES if code not in ("COMPLETED", "CLOSED")]
    data = [stages.get(code, 0) for code, _l in Applicant.STAGE_CHOICES if code not in ("COMPLETED", "CLOSED")]
    offers = ApplicantOffer.objects.filter(applicant__in=visible_applicants(ctx.request, ctx.org))
    month = Q(created_at__gte=day_start(ctx.month_first), created_at__lt=day_end_exclusive(ctx.month_last))
    responded = Q(responded_at__gte=day_start(ctx.month_first), responded_at__lt=day_end_exclusive(ctx.month_last))
    return {
        "open_applicants": sum(data),
        "funnel": chart("bar", labels, [{"name": "Applicants", "data": data}]),
        "offers_this_month": {
            "created": offers.filter(month).count(),
            "accepted": offers.filter(responded, status="ACCEPTED").count(),
            "declined": offers.filter(responded, status="DECLINED").count(),
        },
        "joining_this_month": qs.filter(joining_date__gte=ctx.month_first, joining_date__lte=ctx.month_last).count(),
    }


def w_helpdesk(ctx):
    from app.helpdesk.services import staff_queryset

    qs = staff_queryset(ctx.request, ctx.org, ctx.employee)
    open_qs = qs.exclude(status__in=("RESOLVED", "CLOSED"))
    by_status = dict((r["status"], r["n"]) for r in qs.values("status").annotate(n=Count("id")))
    cats = open_qs.values("category__name").annotate(n=Count("id")).order_by("-n")
    return {
        "open": open_qs.count(),
        "unassigned": open_qs.filter(assigned_to__isnull=True).count(),
        "by_status": by_status,
        "open_by_category": chart("bar", [c["category__name"] for c in cats],
                                  [{"name": "Open", "data": [c["n"] for c in cats]}]),
    }


def w_assets(ctx):
    from app.assets.models import Asset

    rows = Asset.objects.filter(organization=ctx.org, is_active=True).values("status").annotate(n=Count("id"))
    by_status = {code: 0 for code, _l in Asset.STATUS_CHOICES}
    for r in rows:
        by_status[r["status"]] = r["n"]
    soon = ctx.today + timedelta(days=30)
    return {"total": sum(by_status.values()), "by_status": by_status,
            "warranty_ending_30_days": Asset.objects.filter(organization=ctx.org, is_active=True,
                                                            warranty_until__gte=ctx.today,
                                                            warranty_until__lte=soon).count()}


def w_visitors_today(ctx):
    from app.visitors.models import Visit

    qs = Visit.objects.filter(organization=ctx.org, is_active=True, check_in_at__gte=day_start(ctx.today),
                              check_in_at__lt=day_end_exclusive(ctx.today)).select_related("host")
    return {"total": qs.count(), "inside": qs.filter(check_out_at__isnull=True).count(), "latest": [
        {"id": v.id, "visitor_name": v.visitor_name, "company": v.visitor_company, "purpose": v.purpose,
         "host": emp_name(v.host), "check_in": fmt_time(v.check_in_at), "inside": v.check_out_at is None}
        for v in qs.order_by("-check_in_at")[:5]]}


def w_projects(ctx):
    from app.projects.models import Project, Task

    rows = Project.objects.filter(organization=ctx.org, is_active=True).values("status").annotate(n=Count("id"))
    tasks = Task.objects.filter(organization=ctx.org, is_active=True, project__is_active=True).exclude(status="DONE")
    return {
        "by_status": dict((r["status"], r["n"]) for r in rows),
        "open_tasks": tasks.count(),
        "overdue_tasks": tasks.filter(due_date__lt=ctx.today).count(),
        "due_this_week": tasks.filter(due_date__gte=ctx.today, due_date__lte=ctx.today + timedelta(days=7)).count(),
    }


def w_receivables(ctx):
    from app.payments.models import ProjectPayment, ProjectPaymentTransaction

    live = ProjectPayment.objects.filter(project__organization=ctx.org, project__is_active=True) \
        .exclude(status="CANCELLED")
    sums = live.aggregate(billed=Sum("amount"), received=Sum("paid_amount"), outstanding=Sum("outstanding_amount"))
    overdue = live.filter(outstanding_amount__gt=0, due_date__lt=ctx.today).aggregate(v=Sum("outstanding_amount"))["v"]
    start = (ctx.month_first - timedelta(days=150)).replace(day=1)
    tx = (ProjectPaymentTransaction.objects.filter(payment__project__organization=ctx.org, status="SUCCESS",
                                                   transaction_date__gte=start, transaction_date__lte=ctx.today))
    months, labels = {}, []
    d = start
    while d <= ctx.month_first:
        key = d.strftime("%Y-%m")
        months[key] = ZERO
        labels.append(d.strftime("%b %Y"))
        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    for t in tx.values("transaction_date", "amount"):
        key = t["transaction_date"].strftime("%Y-%m")
        if key in months:
            months[key] += t["amount"]
    return {
        "billed": num(sums["billed"] or ZERO), "received": num(sums["received"] or ZERO),
        "outstanding": num(sums["outstanding"] or ZERO), "overdue": num(overdue or ZERO),
        "collection_trend": chart("bar", labels, [{"name": "Collected", "data": [num(v) for v in months.values()]}]),
    }


def w_expenses(ctx):
    from app.expenses.models import Expense

    qs = Expense.objects.filter(organization=ctx.org, is_active=True, expense_date__gte=ctx.month_first,
                                expense_date__lte=ctx.month_last)
    rows = qs.values("expense_type").annotate(total=Sum("amount")).order_by("-total")
    labels_map = dict(Expense.EXPENSE_TYPE_CHOICES)
    return {
        "month": ctx.month_first.strftime("%Y-%m"),
        "total": num(qs.aggregate(v=Sum("amount"))["v"] or ZERO),
        "unpaid": num(qs.exclude(payment_status="paid").aggregate(v=Sum("amount"))["v"] or ZERO),
        "by_category": chart("bar", [labels_map.get(r["expense_type"], r["expense_type"]) for r in rows],
                             [{"name": "Amount", "data": [num(r["total"]) for r in rows]}]),
    }


# =========================================================
# REGISTRY: (key, needs_employee, codes (any) or None = everyone, function)
# =========================================================
WIDGETS = [
    ("my_today", True, None, w_my_today),
    ("my_month", True, None, w_my_month),
    ("my_leave_balance", True, None, w_my_leave_balance),
    ("my_recent_leaves", True, None, w_my_recent_leaves),
    ("my_work", True, None, w_my_work),
    ("celebrations", False, None, w_celebrations),
    ("upcoming_holidays", False, None, w_upcoming_holidays),
    ("announcements", False, None, w_announcements),
    ("team_today", True, ("attendance.view_team",), w_team_today),
    ("pending_approvals", False, ("leave.approve", "attendance.approve_correction"), w_pending_approvals),
    ("org_today", False, ("attendance.view_all",), w_org_today),
    ("attendance_trend", False, ("attendance.view_all",), w_attendance_trend),
    ("recent_leave_requests", False, ("leave.view_all",), w_recent_leave_requests),
    ("headcount", False, ("employee.view_all",), w_headcount),
    ("payroll_summary", False, ("payroll.view_all",), w_payroll_summary),
    ("recruitment_pipeline", False, ("applicant.view",), w_recruitment_pipeline),
    ("helpdesk", False, ("ticket.manage", "ticket.handle"), w_helpdesk),
    ("assets", False, ("asset.view", "asset.manage"), w_assets),
    ("visitors_today", False, ("visitor.manage",), w_visitors_today),
    ("projects", False, ("project.manage",), w_projects),
    ("receivables", False, ("payment.manage",), w_receivables),
    ("expenses", False, ("expense.manage",), w_expenses),
]


def available_widgets(ctx):
    out = []
    for key, needs_emp, codes, _fn in WIDGETS:
        if needs_emp and ctx.employee is None:
            continue
        if codes and not ctx.can(*codes):
            continue
        out.append(key)
    return out


def build_dashboard(request, organization, month=None, only=None):
    today = timezone.localdate()
    ref = month or today
    first, last = month_bounds(ref)
    ctx = Ctx(request, organization, today, first, last)
    allowed = available_widgets(ctx)
    wanted = [w for w in allowed if not only or w in only]
    functions = {k: fn for k, _e, _c, fn in WIDGETS}
    widgets, failed = {}, []
    for key in wanted:
        try:
            widgets[key] = functions[key](ctx)
        except Exception:
            logger.exception("Dashboard widget %s failed", key)
            failed.append(key)
    return {
        "generated_at": timezone.localtime().isoformat(),
        "month": first.strftime("%Y-%m"),
        "available_widgets": allowed,
        "widgets": widgets,
        "failed_widgets": failed,
    }
