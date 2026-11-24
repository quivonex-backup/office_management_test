
from django.urls import path
from .views import (
    AttendanceSettingsAPIView,
    ShiftListAPIView, ShiftCreateAPIView, ShiftUpdateAPIView, ShiftDeactivateAPIView,
    EmployeeShiftAssignmentListAPIView, EmployeeShiftAssignmentCreateAPIView, EmployeeShiftAssignmentUpdateAPIView,
    EmployeeShiftAssignmentBulkAPIView, EmployeeShiftAssignmentPatternAPIView, EmployeeShiftAssignmentBulkCloseAPIView,
    AttendancePunchAPIView, AttendanceListAPIView, MyAttendanceListAPIView, MyShiftAssignmentListAPIView, AttendanceDetailAPIView, AttendanceBulkMarkAbsentAPIView,
    AttendanceCorrectionCreateAPIView, AttendanceCorrectionListAPIView, AttendanceCorrectionReviewAPIView,
    MyAttendanceCorrectionAPIView, FaceRecognitionAPIView,
    AttendanceDeviceCreateAPIView, AttendanceDeviceListAPIView, AttendanceDeviceUpdateAPIView,
    AttendanceDeviceResetPasswordAPIView, AttendanceDeviceDeactivateAPIView,
    KioskLoginAPIView, KioskPunchAPIView,
)

# ---------------------------------------------------------------------------
# Who calls what:
#   #SU  super admin (platform)        #A  organization admin side
#   #E   employee self-service         #PUB public (no token)   #DEV debug only
#   #KIOSK  attendance device: "Authorization: Device <token>" from kiosk/login
#   perm: <code>  enforced permission code (organization owner always passes;
#                 others need an access role that has the code)
# ---------------------------------------------------------------------------
urlpatterns = [
    # Settings
    path("settings/", AttendanceSettingsAPIView.as_view()),                                             #A  perm: settings.manage

    # Shifts
    path("shifts/list/", ShiftListAPIView.as_view()),                                                   #A  perm: settings.manage, attendance.view_all, attendance.view_team, attendance.correct (any)
    path("shifts/create/", ShiftCreateAPIView.as_view()),                                               #A  perm: settings.manage
    path("shifts/update/", ShiftUpdateAPIView.as_view()),                                               #A  perm: settings.manage
    path("shifts/deactivate/", ShiftDeactivateAPIView.as_view()),                                       #A  perm: settings.manage

    # Employee shift assignments
    path("shift-assignments/list/", EmployeeShiftAssignmentListAPIView.as_view()),                      #A  perm: settings.manage, attendance.view_all, attendance.view_team, attendance.correct (any)
    path("shift-assignments/create/", EmployeeShiftAssignmentCreateAPIView.as_view()),                  #A  perm: settings.manage
    path("shift-assignments/update/", EmployeeShiftAssignmentUpdateAPIView.as_view()),                  #A  perm: settings.manage

    # Employee shift assignments
    path("shift-assignments/bulk-assign/", EmployeeShiftAssignmentBulkAPIView.as_view()),               #A  perm: settings.manage
    path("shift-assignments/bulk-assign-pattern/", EmployeeShiftAssignmentPatternAPIView.as_view()),    #A  perm: settings.manage
    path("shift-assignments/bulk-close/", EmployeeShiftAssignmentBulkCloseAPIView.as_view()),           #A  perm: settings.manage

    # Attendance
    path("punch/", AttendancePunchAPIView.as_view()),                                                   #E
    path("list/", AttendanceListAPIView.as_view()),                                                     #A  scope: self|team|all (attendance.view_*)
    path("my-attendance/", MyAttendanceListAPIView.as_view()),                                          #E
    path("my-shifts/", MyShiftAssignmentListAPIView.as_view()),                                         #E
    path("detail/", AttendanceDetailAPIView.as_view()),                                                 #E #A  own record, or in team/all scope
    path("bulk-mark-absent/", AttendanceBulkMarkAbsentAPIView.as_view()),                               #A  perm: attendance.correct  dates up to yesterday

    # Corrections
    path("corrections/create/", AttendanceCorrectionCreateAPIView.as_view()),                           #E  own record (attendance.correct for others)
    path("corrections/list/", AttendanceCorrectionListAPIView.as_view()),                               #E #A  scope: self|team|all (attendance.view_*)
    path("corrections/review/", AttendanceCorrectionReviewAPIView.as_view()),                           #A  perm: attendance.approve_correction  + record in caller's scope, not own
    path("my-attendance/correct/", MyAttendanceCorrectionAPIView.as_view()),                            #E

    # Face Recognize
    path("face-recognition/", FaceRecognitionAPIView.as_view()),                                        #E

    # Attendance devices (kiosk tablets)
    path("device/create/", AttendanceDeviceCreateAPIView.as_view()),                                    #A  perm: attendance.device_manage
    path("device/list/", AttendanceDeviceListAPIView.as_view()),                                        #A  perm: attendance.device_manage  (shows passwords)
    path("device/update/", AttendanceDeviceUpdateAPIView.as_view()),                                    #A  perm: attendance.device_manage
    path("device/reset-password/", AttendanceDeviceResetPasswordAPIView.as_view()),                     #A  perm: attendance.device_manage  (logs the device out)
    path("device/deactivate/", AttendanceDeviceDeactivateAPIView.as_view()),                            #A  perm: attendance.device_manage  (logs the device out)

    # Kiosk (device login, no user)
    path("kiosk/login/", KioskLoginAPIView.as_view()),                                                  #KIOSK  device_code + password -> device token
    path("kiosk/punch/", KioskPunchAPIView.as_view()),                                                  #KIOSK  Authorization: Device <token>
]
