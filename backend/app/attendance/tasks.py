
# from datetime import timedelta

# from celery import shared_task
# from django.db import transaction
# from django.utils import timezone

# from app.employees.models import Employee
# from app.calendar_app.services import get_calendar_day

# from .models import AttendanceSettings, AttendanceRecord
# from .services import (
#     get_employee_shift,
#     get_shift_datetimes,
#     mark_employee_absent,
# )


# # An employee may check out up to four hours after the scheduled end.
# # For overnight shifts, scheduled_end is on the following calendar day.
# STALE_CHECKOUT_GRACE_HOURS = 4

# # Fallback only when an attendance record has no scheduled_end.
# STALE_CHECKOUT_FALLBACK_HOURS = 18


# # =========================================================
# # AUTO MARK ABSENT
# # =========================================================

# @shared_task(name="app.attendance.tasks.auto_mark_absent_task")
# def auto_mark_absent_task():
#     """
#     Mark employees absent after their configured cutoff.

#     Rules:
#     - Process the current local work date only.
#     - Process active employees belonging to the organization.
#     - Require an active shift assignment.
#     - Skip holidays and weekly offs.
#     - Respect the configured absence cutoff.
#     - Never overwrite an existing check-in or another attendance status.
#     - Approved leave is already marked ON_LEAVE by the Leave service.
#     - Delegate attendance creation and absence marking to the service.
#     """

#     now = timezone.now()
#     work_date = timezone.localdate(now)

#     organizations_checked = 0
#     employees_checked = 0
#     employees_marked_absent = 0
#     employees_skipped = 0

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
#         ).iterator(chunk_size=500)

#         for employee in employees:
#             employees_checked += 1

#             # Resolve the employee's assigned shift for this work date.
#             shift = get_employee_shift(
#                 employee=employee,
#                 organization=organization,
#                 work_date=work_date,
#             )

#             # Do not mark employees absent when no shift is assigned.
#             if shift is None:
#                 employees_skipped += 1
#                 continue

#             # Check organization holidays and shift-specific weekly offs.
#             calendar_day = get_calendar_day(
#                 organization=organization,
#                 target_date=work_date,
#                 shift=shift,
#             )

#             if calendar_day["day_type"] != "WORKING_DAY":
#                 employees_skipped += 1
#                 continue

#             # Determine the scheduled start using the assigned shift.
#             scheduled_start, _ = get_shift_datetimes(
#                 shift=shift,
#                 work_date=work_date,
#                 attendance_settings=attendance_settings,
#             )

#             absence_cutoff = scheduled_start + timedelta(
#                 minutes=attendance_settings.absent_after_minutes
#             )

#             # Do not mark absent before the configured cutoff.
#             if now < absence_cutoff:
#                 continue

#             # Check whether attendance already exists for this work date.
#             existing_attendance = (
#                 AttendanceRecord.objects.filter(
#                     organization=organization,
#                     employee=employee,
#                     work_date=work_date,
#                 )
#                 .first()
#             )

#             if existing_attendance:
#                 # Never mark an employee absent after they have checked in.
#                 if existing_attendance.check_in:
#                     continue

#                 # This also skips approved leave because its status is ON_LEAVE.
#                 # Do not overwrite ABSENT, ON_LEAVE, HOLIDAY, WEEKLY_OFF,
#                 # PENDING_REVIEW, or any other existing status.
#                 if existing_attendance.status != "INCOMPLETE":
#                     employees_skipped += 1
#                     continue

#             # The service is responsible for creating or updating the record.
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
#         "employees_skipped": employees_skipped,
#     }


# # =========================================================
# # FLAG STALE ATTENDANCE
# # =========================================================

# @shared_task(name="app.attendance.tasks.flag_stale_attendance_task")
# def flag_stale_attendance_task():
#     """
#     Flag attendance records for admin review when an employee has
#     checked in but has not checked out before the allowed deadline.

#     Rules:
#     - Never fabricate a checkout timestamp.
#     - Never modify finalized attendance.
#     - Recheck the record under a database lock before updating it.
#     - Preserve records that have already been checked out or reviewed.
#     - Clear overtime approval while the record awaits review.
#     """

#     now = timezone.now()

#     records_checked = 0
#     records_flagged = 0

#     open_records = (
#         AttendanceRecord.objects.filter(
#             check_in__isnull=False,
#             check_out__isnull=True,
#             status="INCOMPLETE",
#         )
#         .exclude(calculation_status="FINALIZED")
#         .order_by("pk")
#         .values_list("pk", flat=True)
#         .iterator(chunk_size=500)
#     )

#     for attendance_id in open_records:
#         records_checked += 1

#         with transaction.atomic():
#             # Lock and re-fetch the record because an employee may have
#             # checked out after the initial query.
#             attendance = (
#                 AttendanceRecord.objects
#                 .select_for_update()
#                 .filter(pk=attendance_id)
#                 .first()
#             )

#             if attendance is None:
#                 continue

#             # Recheck all conditions after obtaining the database lock.
#             if (
#                 attendance.check_in is None
#                 or attendance.check_out is not None
#                 or attendance.status != "INCOMPLETE"
#                 or attendance.calculation_status == "FINALIZED"
#             ):
#                 continue

#             if attendance.scheduled_end is not None:
#                 checkout_deadline = (
#                     attendance.scheduled_end
#                     + timedelta(hours=STALE_CHECKOUT_GRACE_HOURS)
#                 )
#             else:
#                 # Fallback for legacy or incomplete attendance records.
#                 checkout_deadline = (
#                     attendance.check_in
#                     + timedelta(hours=STALE_CHECKOUT_FALLBACK_HOURS)
#                 )

#             # Continue waiting if the allowed checkout period has not passed.
#             if now <= checkout_deadline:
#                 continue

#             attendance.status = "PENDING_REVIEW"
#             attendance.calculation_status = "PENDING"

#             # Overtime must not be approved automatically for an
#             # attendance record whose checkout is missing.
#             attendance.calculated_overtime_minutes = 0
#             attendance.approved_overtime_minutes = 0
#             attendance.overtime_is_approved = False
#             attendance.overtime_approved_at = None

#             attendance.save(
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
