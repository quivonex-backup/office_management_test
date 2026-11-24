"""
Shared pieces for the reports app (read-only aggregation across apps).

- period parsing (from_date / to_date, default = current month)
- local-day datetime bounds (no __date lookups: MySQL time zone tables)
- organization features (branches / departments / payroll mode ...) so
  reports only return columns and filters that mean something
- employee scope (all / team) from the existing view codes
- one report shape for JSON + an Excel writer built from the same data
"""
import calendar
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from common.exports import xlsx_response  # noqa: F401  (re-exported for the views)

ZERO = Decimal("0")
MAX_RANGE_DAYS = 366
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500


class ReportError(Exception):
    def __init__(self, message, http_status=400):
        super().__init__(message)
        self.http_status = http_status


# =========================================================
# DATES
# =========================================================
def month_bounds(day):
    first = day.replace(day=1)
    last = day.replace(day=calendar.monthrange(day.year, day.month)[1])
    return first, last


def parse_day(value, field):
    if value in (None, ""):
        return None
    try:
        day = parse_date(str(value))
    except ValueError:
        day = None
    if day is None:
        raise ReportError(f"{field} must use YYYY-MM-DD format.")
    return day


def parse_period(data, today=None):
    """from_date / to_date; both default to the current month."""
    today = today or timezone.localdate()
    first, last = month_bounds(today)
    from_date = parse_day(data.get("from_date"), "from_date") or first
    to_date = parse_day(data.get("to_date"), "to_date") or last
    if from_date > to_date:
        raise ReportError("from_date cannot be after to_date.")
    if (to_date - from_date).days >= MAX_RANGE_DAYS:
        raise ReportError(f"The date range can be at most {MAX_RANGE_DAYS} days.")
    return from_date, to_date


def day_start(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def day_end_exclusive(day):
    return timezone.make_aware(datetime.combine(day + timedelta(days=1), time.min))


def days_between(from_date, to_date):
    day = from_date
    while day <= to_date:
        yield day
        day += timedelta(days=1)


def fmt_time(value):
    if not value:
        return None
    return timezone.localtime(value).strftime("%H:%M")


def minutes_to_hours(minutes):
    return float((Decimal(minutes or 0) / Decimal(60)).quantize(Decimal("0.01")))


def num(value):
    """Decimal -> float for JSON / Excel; None stays None."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return value


# =========================================================
# ORGANIZATION FEATURES
# =========================================================
def org_features(organization):
    from app.accounts.models import Branch
    from app.employees.models import Department, Designation, Employee
    from app.payroll.models import CompanyStatutorySettings, PayrollSettings

    payroll = PayrollSettings.objects.filter(organization=organization).first()
    statutory = CompanyStatutorySettings.objects.filter(organization=organization).first()
    full = bool(payroll and payroll.payslip_mode == "FULL")
    return {
        "has_branches": Branch.objects.filter(organization=organization, is_active=True).exists(),
        "has_departments": Department.objects.filter(organization=organization, is_active=True).exists(),
        "has_designations": Designation.objects.filter(organization=organization, is_active=True).exists(),
        "has_remote": Employee.objects.filter(organization=organization, is_active=True,
                                              attendance_location_exempt=True).exists(),
        "payslip_mode": payroll.payslip_mode if payroll else "SIMPLE",
        "overtime_enabled": bool(payroll.overtime_enabled) if payroll else True,
        "late_deduction_enabled": bool(getattr(payroll, "late_deduction_enabled", False)),
        "pf": full and bool(statutory and statutory.is_pf_applicable),
        "vpf": full and bool(statutory and statutory.is_pf_applicable
                             and statutory.pf_contribution_type == "VPF"),
        "esi": full and bool(statutory and statutory.is_esi_applicable),
        "pt": full and bool(statutory and statutory.is_pt_applicable),
        "lwf": full and bool(statutory and statutory.is_lwf_applicable),
    }


# =========================================================
# EMPLOYEE SCOPE + FILTERS
# =========================================================
def employee_scope(request, organization, all_code, team_code=None):
    """
    (employee_ids or None for everyone, scope name). Reports need the all /
    team code; self-only users are refused (their data is on the dashboard).
    """
    from common.permissions import has_perm, get_user_employee
    from common.services import get_team_employee_ids

    if all_code and has_perm(request, organization, all_code):
        return None, "all"
    if team_code and has_perm(request, organization, team_code):
        employee = get_user_employee(request.user, organization)
        if employee is not None:
            return get_team_employee_ids(employee), "team"
    raise ReportError("You do not have permission to view this report.", http_status=403)


def apply_employee_filters(qs, data, features, prefix="employee__", ids=None):
    """department_id / branch_id / designation_id / employee_id / search on an employee relation."""
    p = prefix
    if ids is not None:
        qs = qs.filter(**{f"{p}id__in": ids}) if p else qs.filter(id__in=ids)
    if data.get("employee_id"):
        qs = qs.filter(**{f"{p}id": data.get("employee_id")})
    if data.get("department_id") and features["has_departments"]:
        qs = qs.filter(**{f"{p}department_ref_id": data.get("department_id")})
    if data.get("branch_id") and features["has_branches"]:
        qs = qs.filter(**{f"{p}branch_id": data.get("branch_id")})
    if data.get("designation_id") and features["has_designations"]:
        qs = qs.filter(**{f"{p}designation_ref_id": data.get("designation_id")})
    search = (data.get("search") or "").strip()
    if search:
        qs = qs.filter(
            Q(**{f"{p}first_name__icontains": search}) | Q(**{f"{p}last_name__icontains": search})
            | Q(**{f"{p}employee_code__icontains": search})
        )
    return qs


def emp_name(emp):
    if emp is None:
        return None
    return " ".join(p for p in [emp.first_name, emp.middle_name, emp.last_name] if p)


def dept_name(emp):
    ref = getattr(emp, "department_ref", None)
    return ref.name if ref else (getattr(emp, "department", None) or None)


def branch_name(emp):
    ref = getattr(emp, "branch", None)
    return ref.name if ref else None


# =========================================================
# REPORT SHAPE
# =========================================================
def col(key, label, kind="text", optional=None):
    """
    kind: text | number | money | date | time | bool
    optional:
      None    always shown
      "data"  shown only when some row has a non-empty, non-zero value
      bool    an organization setting: True keeps it; False drops it unless
              the data still has values (e.g. an older payroll run)
    """
    return {"key": key, "label": label, "type": kind, "_optional": optional}


def _has_data(rows, key):
    return any(r.get(key) not in (None, "", 0, 0.0, False) for r in rows)


def finalize_columns(columns, rows):
    keep = []
    for c in columns:
        opt = c.get("_optional")
        if opt is None:
            keep.append(c)
        elif opt == "data":
            if _has_data(rows, c["key"]):
                keep.append(c)
        elif opt or _has_data(rows, c["key"]):
            keep.append(c)
    return [{k: v for k, v in c.items() if k != "_optional"} for c in keep]


def chart(kind, labels, series):
    return {"type": kind, "labels": labels, "series": series}


def build_report(*, key, title, filters, columns, rows, totals=None, chart_data=None, data=None,
                 extra=None):
    columns = finalize_columns(columns, rows)
    keys = {c["key"] for c in columns}
    if totals:
        totals = {k: v for k, v in totals.items() if k in keys}
    report = {
        "report": key,
        "title": title,
        "filters": filters,
        "columns": columns,
        "rows": [{k: r.get(k) for k in [c["key"] for c in columns]} for r in rows],
        "totals": totals or {},
        "chart": chart_data,
    }
    if extra:
        report.update(extra)
    return report


def paginate(report, data):
    rows = report["rows"]
    try:
        page = max(int(data.get("page") or 1), 1)
        size = min(max(int(data.get("page_size") or DEFAULT_PAGE_SIZE), 1), MAX_PAGE_SIZE)
    except (TypeError, ValueError):
        raise ReportError("page and page_size must be numbers.")
    total = len(rows)
    report["rows"] = rows[(page - 1) * size: page * size]
    report["pagination"] = {"page": page, "page_size": size, "total_rows": total,
                            "total_pages": (total + size - 1) // size if total else 0}
    return report
