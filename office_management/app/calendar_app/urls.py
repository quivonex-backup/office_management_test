from django.urls import path

from .views import (
    WeeklyOffRuleListAPIView,
    WeeklyOffRuleCreateAPIView,
    WeeklyOffRuleUpdateAPIView,
    WeeklyOffRuleDeactivateAPIView,
    CalendarHolidayListAPIView,
    CalendarHolidayCreateAPIView,
    CalendarHolidayUpdateAPIView,
    CalendarHolidayDeactivateAPIView,
    EmployeeCalendarAPIView,
)


urlpatterns = [
    # Weekly-off rules
    path("weekly-offs/list/", WeeklyOffRuleListAPIView.as_view(), name="weekly-off-list"),
    path("weekly-offs/create/", WeeklyOffRuleCreateAPIView.as_view(), name="weekly-off-create"),
    path("weekly-offs/update/", WeeklyOffRuleUpdateAPIView.as_view(), name="weekly-off-update"),
    path("weekly-offs/deactivate/", WeeklyOffRuleDeactivateAPIView.as_view(), name="weekly-off-deactivate"),

    # Organization holidays
    path("holidays/list/", CalendarHolidayListAPIView.as_view(), name="calendar-holiday-list"),
    path("holidays/create/", CalendarHolidayCreateAPIView.as_view(), name="calendar-holiday-create"),
    path("holidays/update/", CalendarHolidayUpdateAPIView.as_view(), name="calendar-holiday-update"),
    path("holidays/deactivate/", CalendarHolidayDeactivateAPIView.as_view(), name="calendar-holiday-deactivate"),

    # Employee Calendar
    path("employee/", EmployeeCalendarAPIView.as_view(), name="employee-calendar"),
]