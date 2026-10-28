
# from datetime import timedelta

# from celery import shared_task
# from django.db import transaction
# from django.utils import timezone

# from app.employees.models import Employee

# from .models import AttendanceSettings, AttendanceRecord
# from .services import (
#     get_employee_shift,
#     get_shift_datetimes,
#     mark_employee_absent,
# )


# # An employee may check out up to four hours after the scheduled end.
# # For overnight shifts, scheduled_end is on the following calendar day.
# STALE_CHECKOUT_GRACE_HOURS = 4


# @shared_task(name="app.attendance.tasks.auto_mark_absent_task")
# def auto_mark_absent_task():
#     """
#     Automatically mark employees absent after their configured cutoff.
#     Currently disabled.
#     """

#     now = timezone.now()
#     work_date = timezone.localdate(now)

#     organizations_checked = 0
#     employees_checked = 0
#     employees_marked_absent = 0

#     settings_list = (
#         AttendanceSettings.objects
#         .filter(auto_mark_absent=True)
#         .select_related("organization")
#     )

#     for attendance_settings in settings_list:
#         organization = attendance_settings.organization
#         organizations_checked += 1

#         employees = Employee.objects.filter(
#             organization=organization,
#             is_active=True,
#             employment_status="ACTIVE",
#         ).iterator()

#         for employee in employees:
#             employees_checked += 1

#             shift = get_employee_shift(
#                 employee,
#                 organization,
#                 work_date,
#             )

#             scheduled_start, _ = get_shift_datetimes(
#                 shift,
#                 work_date,
#                 attendance_settings,
#             )

#             absence_cutoff = scheduled_start + timedelta(
#                 minutes=attendance_settings.absent_after_minutes
#             )

#             if now < absence_cutoff:
#                 continue

#             existing_attendance = AttendanceRecord.objects.filter(
#                 organization=organization,
#                 employee=employee,
#                 work_date=work_date,
#             ).first()

#             if existing_attendance:
#                 if existing_attendance.check_in:
#                     continue

#                 if existing_attendance.status != "INCOMPLETE":
#                     continue

#             attendance = mark_employee_absent(
#                 employee=employee,
#                 organization=organization,
#                 work_date=work_date,
#             )

#             if attendance.status == "ABSENT":
#                 employees_marked_absent += 1

#     return {
#         "status": "completed",
#         "work_date": str(work_date),
#         "organizations_checked": organizations_checked,
#         "employees_checked": employees_checked,
#         "employees_marked_absent": employees_marked_absent,
#     }


# @shared_task(name="app.attendance.tasks.flag_stale_attendance_task")
# def flag_stale_attendance_task():
#     """
#     Flag attendance records with a missing checkout after the
#     scheduled-end grace period. Currently disabled.
#     """

#     now = timezone.now()

#     records_checked = 0
#     records_flagged = 0

#     open_records = (
#         AttendanceRecord.objects
#         .filter(
#             check_in__isnull=False,
#             check_out__isnull=True,
#             status="INCOMPLETE",
#         )
#         .exclude(calculation_status="FINALIZED")
#         .select_related("organization", "employee")
#         .iterator()
#     )

#     for attendance in open_records:
#         records_checked += 1

#         if attendance.scheduled_end:
#             checkout_deadline = (
#                 attendance.scheduled_end
#                 + timedelta(hours=STALE_CHECKOUT_GRACE_HOURS)
#             )
#         else:
#             checkout_deadline = (
#                 attendance.check_in + timedelta(hours=18)
#             )

#         if now <= checkout_deadline:
#             continue

#         with transaction.atomic():
#             locked_attendance = (
#                 AttendanceRecord.objects
#                 .select_for_update()
#                 .filter(pk=attendance.pk)
#                 .first()
#             )

#             if not locked_attendance:
#                 continue

#             if (
#                 not locked_attendance.check_in
#                 or locked_attendance.check_out
#                 or locked_attendance.status != "INCOMPLETE"
#                 or locked_attendance.calculation_status == "FINALIZED"
#             ):
#                 continue

#             if locked_attendance.scheduled_end:
#                 latest_deadline = (
#                     locked_attendance.scheduled_end
#                     + timedelta(hours=STALE_CHECKOUT_GRACE_HOURS)
#                 )
#             else:
#                 latest_deadline = (
#                     locked_attendance.check_in + timedelta(hours=18)
#                 )

#             if now <= latest_deadline:
#                 continue

#             locked_attendance.status = "PENDING_REVIEW"
#             locked_attendance.calculation_status = "PENDING"

#             locked_attendance.calculated_overtime_minutes = 0
#             locked_attendance.approved_overtime_minutes = 0
#             locked_attendance.overtime_is_approved = False
#             locked_attendance.overtime_approved_at = None

#             locked_attendance.save(
#                 update_fields=[
#                     "status",
#                     "calculation_status",
#                     "calculated_overtime_minutes",
#                     "approved_overtime_minutes",
#                     "overtime_is_approved",
#                     "overtime_approved_at",
#                     "updated_at",
#                 ]
#             )

#             records_flagged += 1

#     return {
#         "status": "completed",
#         "checked_at": now.isoformat(),
#         "records_checked": records_checked,
#         "records_flagged_for_review": records_flagged,
#     }
