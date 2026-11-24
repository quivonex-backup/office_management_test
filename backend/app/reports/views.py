"""
Reports & dashboard API (all POST). Read-only: data comes from the other apps.

  dashboard/      everyone (widgets filtered by the caller's codes)
  list/           everyone (only the reports the caller may open)
  attendance/     attendance.view_all | attendance.view_team
  leave/          leave.view_all | leave.view_team
  payroll/        payroll.view_all
  recruitment/    applicant.view

Reports: "format": "json" (default, envelope with columns / rows / totals /
chart / pagination) or "xlsx" (Excel file of all rows, same columns).
"""
from rest_framework import status

from common.permissions import OrgAPIView, RequiredPermsMixin
from common.services import get_user_organization

from .services.common import ReportError, org_features, paginate, parse_day, xlsx_response
from .services.dashboard import WIDGETS, build_dashboard
from .services.registry import REPORTS, allowed_reports


# =========================================================
# SHARED
# =========================================================
class ReportsBaseAPIView(RequiredPermsMixin, OrgAPIView):

    def get_org(self, request):
        return get_user_organization(request)


class ReportAPIView(ReportsBaseAPIView):
    """One report: subclasses set report_key; codes come from the registry."""

    report_key = None

    @property
    def required_perms(self):
        return REPORTS[self.report_key][2]

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        data = request.data
        fmt = str(data.get("format") or "json").lower()
        if fmt not in ("json", "xlsx"):
            return self.fail("format must be json or xlsx.")
        report_fn = REPORTS[self.report_key][4]
        try:
            report = report_fn(request, organization, data, org_features(organization))
            if fmt == "xlsx":
                return xlsx_response(report, organization)
            report = paginate(report, data)
        except ReportError as exc:
            return self.fail(str(exc), http_status=exc.http_status)
        return self.ok("Report generated.", report)


# =========================================================
# DASHBOARD
# =========================================================
class DashboardAPIView(ReportsBaseAPIView):

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        month = None
        raw = request.data.get("month")
        if raw:
            raw = str(raw).strip()
            try:
                month = parse_day(f"{raw}-01" if len(raw) == 7 else raw, "month")
            except ReportError as exc:
                return self.fail(str(exc))
        only = request.data.get("widgets") or None
        if only is not None:
            if isinstance(only, str):
                only = [w.strip() for w in only.split(",") if w.strip()]
            known = {w[0] for w in WIDGETS}
            unknown = [w for w in only if w not in known]
            if unknown:
                return self.fail("Unknown widgets.", {"widgets": [f"Unknown: {', '.join(unknown)}"]})
        return self.ok("Dashboard fetched.", build_dashboard(request, organization, month=month, only=only))


# =========================================================
# REPORT LIST
# =========================================================
class ReportListAPIView(ReportsBaseAPIView):

    def post(self, request):
        organization, err = self.get_org(request)
        if err:
            return err
        features = org_features(organization)
        return self.ok("Reports fetched.", {
            "reports": allowed_reports(request, organization, features),
            "organization_features": {
                "has_branches": features["has_branches"],
                "has_departments": features["has_departments"],
                "has_designations": features["has_designations"],
                "payslip_mode": features["payslip_mode"],
            },
        })


# =========================================================
# REPORTS
# =========================================================
class AttendanceReportAPIView(ReportAPIView):
    report_key = "attendance"


class LeaveReportAPIView(ReportAPIView):
    report_key = "leave"


class PayrollReportAPIView(ReportAPIView):
    report_key = "payroll"


class RecruitmentReportAPIView(ReportAPIView):
    report_key = "recruitment"
