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


urlpatterns = [
    # Weekly-off rules
    path("weekly-offs/list/", WeeklyOffRuleListAPIView.as_view()),
    path("weekly-offs/create/", WeeklyOffRuleCreateAPIView.as_view()),
    path("weekly-offs/update/", WeeklyOffRuleUpdateAPIView.as_view()),
    path("weekly-offs/deactivate/", WeeklyOffRuleDeactivateAPIView.as_view()),

    path("weekly-offs/bulk-create/", WeeklyOffRuleBulkCreateAPIView.as_view()),

    # Organization holidays
    path("holidays/list/", CalendarHolidayListAPIView.as_view()),
    path("holidays/create/", CalendarHolidayCreateAPIView.as_view()),
    path("holidays/update/", CalendarHolidayUpdateAPIView.as_view()),
    path("holidays/deactivate/", CalendarHolidayDeactivateAPIView.as_view()),
    path("holidays/bulk-import/", CalendarHolidayBulkImportAPIView.as_view()),

    # Employee Calendar
    path("employee/", EmployeeCalendarAPIView.as_view()),
]