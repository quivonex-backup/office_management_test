"""
Report catalogue for reports/list/: which reports the caller may open and the
filters that apply to this organization (no branch filter without branches...).
"""
from common.permissions import has_perm

from .attendance import attendance_report
from .leave import leave_report
from .payroll import payroll_report
from .recruitment import recruitment_report


def _common_people_filters(features):
    out = [
        {"key": "from_date", "type": "date", "default": "first day of this month"},
        {"key": "to_date", "type": "date", "default": "last day of this month"},
        {"key": "employee_id", "type": "employee"},
    ]
    if features["has_departments"]:
        out.append({"key": "department_id", "type": "department"})
    if features["has_branches"]:
        out.append({"key": "branch_id", "type": "branch"})
    if features["has_designations"]:
        out.append({"key": "designation_id", "type": "designation"})
    out.append({"key": "search", "type": "text"})
    return out


def _attendance_filters(features):
    return _common_people_filters(features) + [
        {"key": "view", "type": "choice", "options": ["summary", "daily"], "default": "summary"},
        {"key": "status", "type": "choice",
         "options": ["PRESENT", "HALF_DAY", "ABSENT", "ON_LEAVE", "INCOMPLETE", "PENDING_REVIEW", "HOLIDAY",
                     "WEEKLY_OFF"]},
        {"key": "late_only", "type": "bool"},
        {"key": "early_only", "type": "bool"},
    ] + ([{"key": "overtime_only", "type": "bool"}] if features["overtime_enabled"] else [])


def _leave_filters(features):
    return _common_people_filters(features) + [
        {"key": "view", "type": "choice", "options": ["taken", "balance"], "default": "taken"},
        {"key": "leave_type_id", "type": "leave_type"},
        {"key": "status", "type": "choice", "options": ["PENDING", "APPROVED", "REJECTED", "CANCELLED"]},
    ]


def _payroll_filters(features):
    out = [
        {"key": "payroll_run_id", "type": "payroll_run", "default": "latest run"},
        {"key": "month", "type": "month", "note": "YYYY-MM; the run that ends in that month"},
        {"key": "employee_id", "type": "employee"},
    ]
    if features["has_departments"]:
        out.append({"key": "department_id", "type": "department"})
    if features["has_branches"]:
        out.append({"key": "branch_id", "type": "branch"})
    out += [
        {"key": "payment_status", "type": "choice", "options": ["UNPAID", "PARTIALLY_PAID", "PAID"]},
        {"key": "requires_review", "type": "bool"},
        {"key": "search", "type": "text"},
    ]
    return out


def _recruitment_filters(features):
    out = [
        {"key": "from_date", "type": "date", "default": "first day of this month", "note": "applied on"},
        {"key": "to_date", "type": "date", "default": "last day of this month"},
        {"key": "view", "type": "choice", "options": ["applicants", "funnel"], "default": "applicants"},
        {"key": "stage", "type": "choice", "options": ["APPLICANT", "VERIFICATION", "ONBOARDING", "COMPLETED", "CLOSED"]},
        {"key": "status", "type": "choice", "options": ["PENDING", "SHORTLISTED", "SELECTED", "REJECTED", "WITHDRAWN"]},
        {"key": "source", "type": "choice",
         "options": ["JOB_PORTAL", "REFERRAL", "WEBSITE", "WALK_IN", "CAMPUS", "AGENCY", "SOCIAL", "OTHER"]},
        {"key": "designation_id", "type": "designation"},
        {"key": "assigned_to_id", "type": "employee"},
        {"key": "search", "type": "text"},
    ]
    if features["has_departments"]:
        out.insert(7, {"key": "department_id", "type": "department"})
    return out


# key: (title, group, any-of codes, filters builder, report function)
REPORTS = {
    "attendance": ("Attendance", "People", ("attendance.view_all", "attendance.view_team"),
                   _attendance_filters, attendance_report),
    "leave": ("Leave", "People", ("leave.view_all", "leave.view_team"), _leave_filters, leave_report),
    "payroll": ("Payroll (salary register)", "Payroll", ("payroll.view_all",), _payroll_filters, payroll_report),
    "recruitment": ("Recruitment", "Recruitment", ("applicant.view",), _recruitment_filters, recruitment_report),
}


def allowed_reports(request, organization, features):
    out = []
    for key, (title, group, codes, filters_fn, _fn) in REPORTS.items():
        if any(has_perm(request, organization, c) for c in codes):
            out.append({"key": key, "title": title, "group": group, "url": f"/reports/{key}/",
                        "formats": ["json", "xlsx"], "filters": filters_fn(features)})
    return out
