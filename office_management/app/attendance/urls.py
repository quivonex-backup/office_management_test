
from django.urls import path
from .views import (
    AttendanceSettingsAPIView,
    ShiftListAPIView, ShiftCreateAPIView, ShiftUpdateAPIView, ShiftDeactivateAPIView,
    EmployeeShiftAssignmentListAPIView, EmployeeShiftAssignmentCreateAPIView, EmployeeShiftAssignmentUpdateAPIView,
    AttendancePunchAPIView, AttendanceListAPIView, MyAttendanceListAPIView, AttendanceDetailAPIView,
    AttendanceCorrectionCreateAPIView, AttendanceCorrectionListAPIView, AttendanceCorrectionReviewAPIView,
    FaceRecognitionAPIView
)

urlpatterns = [
    # Settings
    path("settings/", AttendanceSettingsAPIView.as_view()),

    # Shifts
    path("shifts/list/", ShiftListAPIView.as_view()),
    path("shifts/create/", ShiftCreateAPIView.as_view()),
    path("shifts/update/", ShiftUpdateAPIView.as_view()),
    path("shifts/deactivate/", ShiftDeactivateAPIView.as_view()),

    # Employee shift assignments
    path("shift-assignments/list/", EmployeeShiftAssignmentListAPIView.as_view()),
    path("shift-assignments/create/", EmployeeShiftAssignmentCreateAPIView.as_view()),
    path("shift-assignments/update/", EmployeeShiftAssignmentUpdateAPIView.as_view()),

    # Attendance
    path("punch/", AttendancePunchAPIView.as_view()),
    path("list/", AttendanceListAPIView.as_view()),
    path("my-attendance/", MyAttendanceListAPIView.as_view()),
    path("detail/", AttendanceDetailAPIView.as_view()),

    # Corrections
    path("corrections/create/", AttendanceCorrectionCreateAPIView.as_view()),
    path("corrections/list/", AttendanceCorrectionListAPIView.as_view()),
    path("corrections/review/", AttendanceCorrectionReviewAPIView.as_view()),

    # Face Recognize
    path("face-recognition/", FaceRecognitionAPIView.as_view()),
]
