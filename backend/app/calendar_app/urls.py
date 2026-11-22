from django.urls import path

from .views import (
    WeeklyOffRuleListAPIView,
    WeeklyOffRuleCreateAPIView,
    WeeklyOffRuleUpdateAPIView,
    WeeklyOffRuleDeactivateAPIView,
    WeeklyOffRuleBulkCreateAPIView,
    CalendarHolidayListAPIView,
    CalendarHolidayCreateAPIView,
    CalendarHolidayUpdateAPIView,
    CalendarHolidayDeactivateAPIView,
    CalendarHolidayBulkImportAPIView,
    EmployeeCalendarAPIView,
)


# ---------------------------------------------------------------------------
# Who calls what:
#   #SU  super admin (platform)        #A  organization admin side
#   #E   employee self-service         #PUB public (no token)   #DEV debug only
#   perm: <code>  enforced permission code (organization owner always passes;
#                 others need an access role that has the code)
# ---------------------------------------------------------------------------
urlpatterns = [
    # Weekly-off rules
    path("weekly-offs/list/", WeeklyOffRuleListAPIView.as_view()),                 #A  perm: calendar.manage, settings.manage, attendance.view_all, attendance.view_team (any)
    path("weekly-offs/create/", WeeklyOffRuleCreateAPIView.as_view()),             #A  perm: calendar.manage
    path("weekly-offs/update/", WeeklyOffRuleUpdateAPIView.as_view()),             #A  perm: calendar.manage
    path("weekly-offs/deactivate/", WeeklyOffRuleDeactivateAPIView.as_view()),     #A  perm: calendar.manage

    path("weekly-offs/bulk-create/", WeeklyOffRuleBulkCreateAPIView.as_view()),    #A  perm: calendar.manage

    # Organization holidays
    path("holidays/list/", CalendarHolidayListAPIView.as_view()),                  #E #A
    path("holidays/create/", CalendarHolidayCreateAPIView.as_view()),              #A  perm: calendar.manage
    path("holidays/update/", CalendarHolidayUpdateAPIView.as_view()),              #A  perm: calendar.manage
    path("holidays/deactivate/", CalendarHolidayDeactivateAPIView.as_view()),      #A  perm: calendar.manage
    path("holidays/bulk-import/", CalendarHolidayBulkImportAPIView.as_view()),     #A  perm: calendar.manage

    # Employee Calendar
    path("employee/", EmployeeCalendarAPIView.as_view()),                          #E
]