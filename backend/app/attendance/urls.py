
from django.urls import path
from .views import (
    AttendanceSettingsAPIView,
    ShiftListAPIView, ShiftCreateAPIView, ShiftUpdateAPIView, ShiftDeactivateAPIView,
    EmployeeShiftAssignmentListAPIView, EmployeeShiftAssignmentCreateAPIView, EmployeeShiftAssignmentUpdateAPIView,
    EmployeeShiftAssignmentBulkAPIView, EmployeeShiftAssignmentPatternAPIView, EmployeeShiftAssignmentBulkCloseAPIView,
    AttendancePunchAPIView, AttendanceListAPIView, MyAttendanceListAPIView, MyShiftAssignmentListAPIView, AttendanceDetailAPIView, AttendanceBulkMarkAbsentAPIView,
    AttendanceCorrectionCreateAPIView, AttendanceCorrectionListAPIView, AttendanceCorrectionReviewAPIView,
    MyAttendanceCorrectionAPIView, FaceRecognitionAPIView
)

# ---------------------------------------------------------------------------
# Who calls what:
#   #SU  super admin (platform)        #A  organization admin side
#   #E   employee self-service         #PUB public (no token)   #DEV debug only
#   perm: <code>  enforced permission code (organization owner always passes;
#                 others need an access role that has the code)
# ---------------------------------------------------------------------------
urlpatterns = [
    # Settings
    path("settings/", AttendanceSettingsAPIView.as_view()),                                             #A

    # Shifts
    path("shifts/list/", ShiftListAPIView.as_view()),                                                   #A
    path("shifts/create/", ShiftCreateAPIView.as_view()),                                               #A
    path("shifts/update/", ShiftUpdateAPIView.as_view()),                                               #A
    path("shifts/deactivate/", ShiftDeactivateAPIView.as_view()),                                       #A

    # Employee shift assignments
    path("shift-assignments/list/", EmployeeShiftAssignmentListAPIView.as_view()),                      #A
    path("shift-assignments/create/", EmployeeShiftAssignmentCreateAPIView.as_view()),                  #A
    path("shift-assignments/update/", EmployeeShiftAssignmentUpdateAPIView.as_view()),                  #A

    # Employee shift assignments
    path("shift-assignments/bulk-assign/", EmployeeShiftAssignmentBulkAPIView.as_view()),               #A
    path("shift-assignments/bulk-assign-pattern/", EmployeeShiftAssignmentPatternAPIView.as_view()),    #A
    path("shift-assignments/bulk-close/", EmployeeShiftAssignmentBulkCloseAPIView.as_view()),           #A

    # Attendance
    path("punch/", AttendancePunchAPIView.as_view()),                                                   #E
    path("list/", AttendanceListAPIView.as_view()),                                                     #A
    path("my-attendance/", MyAttendanceListAPIView.as_view()),                                          #E
    path("my-shifts/", MyShiftAssignmentListAPIView.as_view()),                                         #E
    path("detail/", AttendanceDetailAPIView.as_view()),                                                 #E #A
    path("bulk-mark-absent/", AttendanceBulkMarkAbsentAPIView.as_view()),                               #A

    # Corrections
    path("corrections/create/", AttendanceCorrectionCreateAPIView.as_view()),                           #E
    path("corrections/list/", AttendanceCorrectionListAPIView.as_view()),                               #E #A
    path("corrections/review/", AttendanceCorrectionReviewAPIView.as_view()),                           #A
    path("my-attendance/correct/", MyAttendanceCorrectionAPIView.as_view()),                            #E

    # Face Recognize
    path("face-recognition/", FaceRecognitionAPIView.as_view()),                                        #E
]
