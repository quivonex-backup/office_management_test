from django.urls import path

from .views import (
    AttendanceReportAPIView,
    DashboardAPIView,
    EmployeesReportAPIView,
    ExpensesReportAPIView,
    HelpdeskReportAPIView,
    LeaveReportAPIView,
    PayrollReportAPIView,
    ProjectsReportAPIView,
    ReceivablesReportAPIView,
    RecruitmentReportAPIView,
    ReportListAPIView,
)


# ---------------------------------------------------------------------------
# Who calls what:
#   #SU  super admin (platform)        #A  organization admin side
#   #E   employee self-service         #PUB public (no token)   #DEV debug only
#   perm: <code>  enforced permission code (organization owner always passes;
#                 others need an access role that has the code)
#   Reports: "format": "json" | "xlsx" (download) - same permission.
#   *_team codes see only their reportees (reports_to tree).
# ---------------------------------------------------------------------------
urlpatterns = [
    path("dashboard/", DashboardAPIView.as_view(), name="reports-dashboard"),                    #E #A  any employee / owner; widgets filtered by codes
    path("list/", ReportListAPIView.as_view(), name="reports-list"),                             #E #A  any; lists only the reports the caller may open
    path("attendance/", AttendanceReportAPIView.as_view(), name="reports-attendance"),           #A     perm: attendance.view_all, attendance.view_team (any)
    path("leave/", LeaveReportAPIView.as_view(), name="reports-leave"),                          #A     perm: leave.view_all, leave.view_team (any)
    path("payroll/", PayrollReportAPIView.as_view(), name="reports-payroll"),                    #A     perm: payroll.view_all
    path("recruitment/", RecruitmentReportAPIView.as_view(), name="reports-recruitment"),        #A     perm: applicant.view
    path("employees/", EmployeesReportAPIView.as_view(), name="reports-employees"),              #A     perm: employee.view_all, employee.view_team (any)
    path("expenses/", ExpensesReportAPIView.as_view(), name="reports-expenses"),                 #A     perm: reimbursement.review, reimbursement.pay, expense.manage (any; view per code)
    path("receivables/", ReceivablesReportAPIView.as_view(), name="reports-receivables"),        #A     perm: payment.manage
    path("projects/", ProjectsReportAPIView.as_view(), name="reports-projects"),                 #A     perm: project.manage
    path("helpdesk/", HelpdeskReportAPIView.as_view(), name="reports-helpdesk"),                 #A     perm: ticket.manage, ticket.handle (any; handle = own department)
]
