import math
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from app.employees.models import Employee

from common.s3_utils import upload_to_s3

from .models import (
    AttendanceSettings,
    Shift,
    EmployeeShiftAssignment,
    AttendanceRecord,
    AttendancePunch,
    AttendanceCorrection,
)

from .face_recognition_service import (
    FaceVerificationError,
    verify_employee_face,
)

# =========================================================
# SETTINGS
# =========================================================

def get_attendance_settings(organization):
    settings_obj, _ = AttendanceSettings.objects.get_or_create(
        organization=organization
    )
    return settings_obj


# =========================================================
# EMPLOYEE
# =========================================================

def get_employee_for_user(user, organization):
    return Employee.objects.filter(
        user=user,
        organization=organization,
        is_active=True,
        employment_status="ACTIVE",
    ).first()


def get_employee_for_organization(employee_id, organization):
    return Employee.objects.filter(
        id=employee_id,
        organization=organization,
        is_active=True,
        employment_status="ACTIVE",
    ).first()


# =========================================================
# LOCATION VERIFICATION
# =========================================================

def calculate_distance_meters(lat1, lon1, lat2, lon2):
    earth_radius = 6371000

    lat1 = math.radians(float(lat1))
    lon1 = math.radians(float(lon1))
    lat2 = math.radians(float(lat2))
    lon2 = math.radians(float(lon2))

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius * c


def verify_office_location(
    organization,
    latitude,
    longitude,
    gps_accuracy_meters,
    attendance_settings,
):
    if not attendance_settings.location_required:
        return {
            "verified": True,
            "distance_meters": None,
            "message": "Location verification is disabled.",
        }

    if latitude is None or longitude is None:
        return {
            "verified": False,
            "distance_meters": None,
            "message": "GPS coordinates are required.",
        }

    if (
        organization.latitude is None
        or organization.longitude is None
    ):
        return {
            "verified": False,
            "distance_meters": None,
            "message": "Company office coordinates are not configured.",
        }

    # Validate GPS accuracy only when provided.
    if gps_accuracy_meters is not None:
        if (
            gps_accuracy_meters
            > attendance_settings.max_gps_accuracy_meters
        ):
            return {
                "verified": False,
                "distance_meters": None,
                "message": "GPS accuracy is insufficient.",
            }

    distance = calculate_distance_meters(
        organization.latitude,
        organization.longitude,
        latitude,
        longitude,
    )

    allowed_radius = attendance_settings.allowed_radius_meters

    return {
        "verified": distance <= allowed_radius,
        "distance_meters": round(distance, 2),
        "message": (
            "Location verified."
            if distance <= allowed_radius
            else "You are outside the permitted attendance location."
        ),
    }


# =========================================================
# SHIFT AND SCHEDULE
# =========================================================

def get_employee_shift(employee, organization, work_date):
    assignment = (
        EmployeeShiftAssignment.objects.filter(
            organization=organization,
            employee=employee,
            shift__organization=organization,
            shift__is_active=True,
            effective_from__lte=work_date,
        )
        .filter(
            models_q_effective_to(work_date)
        )
        .select_related("shift")
        .order_by("-effective_from")
        .first()
    )

    return assignment.shift if assignment else None


def models_q_effective_to(work_date):
    from django.db.models import Q

    return Q(effective_to__isnull=True) | Q(
        effective_to__gte=work_date
    )


def get_shift_datetimes(shift, work_date, attendance_settings):
    if shift:
        start_time = shift.start_time
        end_time = shift.end_time
    else:
        start_time = attendance_settings.default_start_time
        end_time = attendance_settings.default_end_time

    scheduled_start = timezone.make_aware(
        datetime.combine(work_date, start_time),
        timezone.get_current_timezone(),
    )

    crosses_midnight = (
        shift.crosses_midnight
        if shift
        else end_time < start_time
    )

    end_date = (
        work_date + timedelta(days=1)
        if crosses_midnight or end_time < start_time
        else work_date
    )

    scheduled_end = timezone.make_aware(
        datetime.combine(end_date, end_time),
        timezone.get_current_timezone(),
    )

    return scheduled_start, scheduled_end


# =========================================================
# CREATE ATTENDANCE RECORD
# =========================================================

def get_or_create_attendance(employee, organization, work_date):
    attendance_settings = get_attendance_settings(organization)

    shift = get_employee_shift(
        employee,
        organization,
        work_date,
    )

    scheduled_start, scheduled_end = get_shift_datetimes(
        shift,
        work_date,
        attendance_settings,
    )

    if shift:
        late_grace_minutes = (
            shift.late_grace_minutes
            if shift.late_grace_minutes is not None
            else attendance_settings.late_grace_minutes
        )

        early_departure_grace_minutes = (
            shift.early_departure_grace_minutes
            if shift.early_departure_grace_minutes is not None
            else attendance_settings.early_departure_grace_minutes
        )
    else:
        late_grace_minutes = attendance_settings.late_grace_minutes
        early_departure_grace_minutes = (
            attendance_settings.early_departure_grace_minutes
        )

    attendance, created = AttendanceRecord.objects.get_or_create(
        organization=organization,
        employee=employee,
        work_date=work_date,
        defaults={
            "shift": shift,
            "scheduled_start": scheduled_start,
            "scheduled_end": scheduled_end,
            "late_grace_minutes": late_grace_minutes,
            "early_departure_grace_minutes": early_departure_grace_minutes,
            "status": "INCOMPLETE",
        },
    )

    return attendance


# =========================================================
# CALCULATE ATTENDANCE
# =========================================================


def calculate_attendance(attendance):
    """Update simple attendance facts after a check-in/out or correction.

    - No break deductions.
    - Late/early minutes exclude configured grace periods.
    - Overtime is time after scheduled_end, and is recorded only after checkout.
    - An unfinished or overdue record never gets a fabricated checkout.
    """
    now = timezone.now()
    attendance_settings = get_attendance_settings(attendance.organization)

    if not attendance.check_in:
        attendance.net_work_minutes = 0
        attendance.late_minutes = 0
        attendance.early_departure_minutes = 0
        attendance.overtime_minutes = 0
        attendance.status = "INCOMPLETE"
        attendance.save()
        return attendance

    # Keep overdue attendance pending until a correction supplies the real checkout.
    if attendance.status == "PENDING_REVIEW" and not attendance.check_out:
        attendance.net_work_minutes = 0
        attendance.late_minutes = 0
        attendance.early_departure_minutes = 0
        attendance.overtime_minutes = 0
        attendance.save()
        return attendance

    end_time = attendance.check_out or now
    if end_time < attendance.check_in:
        attendance.status = "PENDING_REVIEW"
        attendance.net_work_minutes = 0
        attendance.overtime_minutes = 0
        attendance.save()
        return attendance

    # Actual elapsed time, without break deductions. For incomplete records this
    # value is temporary; overtime and final status wait for checkout.
    attendance.net_work_minutes = int(
        (end_time - attendance.check_in).total_seconds() // 60
    )

    attendance.late_minutes = 0
    if attendance.scheduled_start:
        late_by = int(
            (attendance.check_in - attendance.scheduled_start).total_seconds() // 60
        )
        attendance.late_minutes = max(0, late_by - attendance.late_grace_minutes)

    attendance.early_departure_minutes = 0
    if attendance.check_out and attendance.scheduled_end:
        early_by = int(
            (attendance.scheduled_end - attendance.check_out).total_seconds() // 60
        )
        attendance.early_departure_minutes = max(
            0, early_by - attendance.early_departure_grace_minutes
        )

    # Do not calculate overtime until the real checkout is known.
    attendance.overtime_minutes = 0
    if attendance.check_out and attendance.scheduled_end:
        attendance.overtime_minutes = max(
            0,
            int((attendance.check_out - attendance.scheduled_end).total_seconds() // 60),
        )

    if not attendance.check_out:
        if attendance.status != "PENDING_REVIEW":
            attendance.status = "INCOMPLETE"
    elif (
        attendance.net_work_minutes < attendance_settings.half_day_threshold_minutes
        or attendance.late_minutes >= attendance_settings.late_half_day_threshold_minutes
        or attendance.early_departure_minutes
        >= attendance_settings.early_departure_half_day_threshold_minutes
    ):
        attendance.status = "HALF_DAY"
    else:
        attendance.status = "PRESENT"

    attendance.save()
    return attendance


# =========================================================
# PROCESS CHECK-IN / CHECK-OUT
# =========================================================



def get_attendance_work_date(employee, organization, now):
    """
    Attribute an after-midnight check-in to yesterday when
    yesterday's assigned overnight shift is still in progress.
    """
    current_date = timezone.localtime(now).date()
    previous_date = current_date - timedelta(days=1)

    attendance_settings = get_attendance_settings(organization)

    previous_shift = get_employee_shift(
        employee,
        organization,
        previous_date,
    )

    if not previous_shift or not previous_shift.crosses_midnight:
        return current_date

    scheduled_start, scheduled_end = get_shift_datetimes(
        previous_shift,
        previous_date,
        attendance_settings,
    )

    if not (scheduled_start <= now < scheduled_end):
        return current_date

    previous_attendance = AttendanceRecord.objects.filter(
        organization=organization,
        employee=employee,
        work_date=previous_date,
    ).first()

    # Do not create a second attendance record for the same shift date.
    if previous_attendance and previous_attendance.check_in:
        return current_date

    return previous_date



@transaction.atomic
def process_attendance_punch(
    employee,
    organization,
    latitude=None,
    longitude=None,
    gps_accuracy_meters=None,
    selfie_file=None,
    recorded_by=None,
):
    now = timezone.now()
    current_date = timezone.localdate(now)

    attendance_settings = get_attendance_settings(organization)

    face_result = {"verified": False, "similarity": None, "threshold": None}
    if attendance_settings.photo_required and not selfie_file:
        raise ValueError("A selfie is required for face verification.")

    if selfie_file:
        try:
            face_result = verify_employee_face(
                employee=employee,
                selfie_file=selfie_file,
            )
        except FaceVerificationError as exc:
            raise ValueError(str(exc)) from exc

        if not face_result["verified"]:
            raise ValueError(
                "Face does not match your registered profile photo."
            )

    location_result = verify_office_location(
        organization=organization,
        latitude=latitude,
        longitude=longitude,
        gps_accuracy_meters=gps_accuracy_meters,
        attendance_settings=attendance_settings,
    )

    if not location_result["verified"]:
        raise ValueError(location_result["message"])

    # Find the latest unfinished attendance, including overdue sessions.
    open_attendance = (
        AttendanceRecord.objects.select_for_update()
        .filter(
            organization=organization,
            employee=employee,
            check_in__isnull=False,
            check_out__isnull=True,
            status="INCOMPLETE",
        )
        .order_by("-check_in")
        .first()
    )

    attendance = None
    punch_type = "CHECK_IN"

    if open_attendance:
        deadline = (
            open_attendance.scheduled_end + timedelta(hours=4)
            if open_attendance.scheduled_end
            else open_attendance.check_in + timedelta(hours=18)
        )

        is_same_work_date = open_attendance.work_date == current_date
        is_overnight_checkout_window = bool(
            open_attendance.shift
            and open_attendance.shift.crosses_midnight
            and now <= deadline
        )

        # Same-day punches may check out after shift end. An overnight shift may
        # also check out on the next calendar day, up to four hours after its
        # scheduled end. A regular previous-day record never consumes today's punch.
        if now <= deadline and (is_same_work_date or is_overnight_checkout_window):
            attendance = open_attendance
            punch_type = "CHECK_OUT"

        else:
            # A same-date second punch cannot create a second attendance row.
            # Raise before changing anything so the atomic transaction is clean.
            if open_attendance.work_date == current_date:
                raise ValueError(
                    "Your attendance is still open for today. Use the correction "
                    "API if you forgot to check out."
                )

            # Previous work date: flag it for correction, then allow today's check-in.
            # Never fabricate a checkout time or keep accumulating overtime.
            open_attendance.status = "PENDING_REVIEW"
            open_attendance.net_work_minutes = 0
            open_attendance.overtime_minutes = 0
            open_attendance.updated_by = recorded_by
            open_attendance.save(
                update_fields=[
                    "status", "net_work_minutes", "overtime_minutes",
                    "updated_by", "updated_at",
                ]
            )

    # If there is no active checkout, determine the correct shift date.
    if punch_type == "CHECK_IN":
        work_date = get_attendance_work_date(
            employee,
            organization,
            now,
        )

        attendance = get_or_create_attendance(
            employee,
            organization,
            work_date,
        )

        if attendance.check_in:
            raise ValueError(
                "Attendance already exists for this work date. "
                "Use the attendance correction request if it is incorrect."
            )

        if attendance.scheduled_end and now >= attendance.scheduled_end:
            raise ValueError(
                "This shift has already ended. Contact your manager "
                "if you need an attendance correction."
            )

    elif attendance.check_out:
        raise ValueError("You have already checked out.")

    # Upload the selfie only after verification and timing checks.
    selfie_path = (
        upload_to_s3(file=selfie_file, folder="attendance/selfies")
        if selfie_file
        else None
    )

    punch = AttendancePunch(
        attendance=attendance,
        punch_type=punch_type,
        punched_at=now,
        latitude=latitude,
        longitude=longitude,
        gps_accuracy_meters=gps_accuracy_meters,
        office_distance_meters=location_result["distance_meters"],
        location_verified=location_result["verified"],
        face_verified=bool(face_result["verified"]),
        face_similarity=face_result["similarity"],
        verification_status="VERIFIED",
        verification_details={
            "location_message": location_result["message"],
            "photo_provided": bool(selfie_file),
            "face_verification": (
                "Verified" if face_result["verified"] else "Skipped"
            ),
            "face_model": "OpenCV SFace" if face_result["verified"] else None,
            "face_similarity": face_result["similarity"],
            "face_threshold": face_result["threshold"],
        },
        recorded_by=recorded_by,
        is_manual=False,
    )

    if selfie_path:
        punch.selfie.name = selfie_path
    punch.save()

    if punch_type == "CHECK_IN":
        attendance.check_in = now
        attendance.created_by = recorded_by
    else:
        attendance.check_out = now

    attendance.updated_by = recorded_by
    attendance.save()

    calculate_attendance(attendance)

    return attendance, punch


# =========================================================
# ATTENDANCE CORRECTION
# =========================================================

@transaction.atomic
def create_attendance_correction(
    attendance,
    field_name,
    new_value,
    reason,
    requested_by,
    punch=None,
):
    allowed_fields = {
        "CHECK_IN",
        "CHECK_OUT",
        "STATUS",
    }

    if field_name not in allowed_fields:
        raise ValueError("Invalid attendance correction field.")

    if punch and punch.attendance_id != attendance.id:
        raise ValueError(
            "The selected punch does not belong to this attendance record."
        )

    field_mapping = {
        "CHECK_IN": "check_in",
        "CHECK_OUT": "check_out",
        "STATUS": "status",
    }

    model_field = field_mapping[field_name]
    old_value = getattr(attendance, model_field)

    if isinstance(old_value, datetime):
        old_value = old_value.isoformat()

    correction = AttendanceCorrection.objects.create(
        attendance=attendance,
        punch=punch,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        reason=reason,
        requested_by=requested_by,
        status="PENDING",
    )

    return correction



@transaction.atomic
def review_attendance_correction(
    correction,
    reviewed_by,
    approve,
    review_note="",
):
    if correction.status != "PENDING":
        raise ValueError("This correction has already been reviewed.")

    correction.reviewed_by = reviewed_by
    correction.reviewed_at = timezone.now()
    correction.review_note = review_note

    if not approve:
        correction.status = "REJECTED"
        correction.save()
        return correction

    attendance = correction.attendance

    field_mapping = {
        "CHECK_IN": "check_in",
        "CHECK_OUT": "check_out",
        "STATUS": "status",
    }

    field_name = correction.field_name

    if field_name not in field_mapping:
        raise ValueError("Invalid correction field.")

    model_field = field_mapping[field_name]
    value = correction.new_value

    if field_name in {"CHECK_IN", "CHECK_OUT"}:
        try:
            value = datetime.fromisoformat(str(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "The corrected time must be a valid ISO 8601 datetime."
            ) from exc

        if timezone.is_naive(value):
            value = timezone.make_aware(
                value,
                timezone.get_current_timezone(),
            )

        # Validate against the other attendance timestamp.
        if field_name == "CHECK_OUT":
            effective_check_in = attendance.check_in

            if effective_check_in and value < effective_check_in:
                raise ValueError(
                    "Check-out cannot be earlier than check-in."
                )

        elif field_name == "CHECK_IN":
            effective_check_out = attendance.check_out

            if effective_check_out and value > effective_check_out:
                raise ValueError(
                    "Check-in cannot be later than check-out."
                )

    elif field_name == "STATUS":
        valid_statuses = {
            choice[0] for choice in AttendanceRecord.STATUS_CHOICES
        }

        if value not in valid_statuses:
            raise ValueError("Invalid attendance status.")

    setattr(attendance, model_field, value)
    attendance.updated_by = reviewed_by

    # If check-in is corrected while a pending-review record still has no
    # checkout, return it to INCOMPLETE so its attendance facts are recalculated.
    if (
        field_name == "CHECK_IN"
        and attendance.check_out is None
        and attendance.status == "PENDING_REVIEW"
    ):
        attendance.status = "INCOMPLETE"

    attendance.save()

    # Recalculate after a time correction, including an overdue session.
    if field_name in {"CHECK_IN", "CHECK_OUT"}:
        calculate_attendance(attendance)

    correction.status = "APPLIED"
    correction.save()

    return correction


# =========================================================
# MARK ABSENT
# Call from a scheduled task after the shift's start/grace period.
# =========================================================

@transaction.atomic
def mark_employee_absent(employee, organization, work_date):
    attendance = get_or_create_attendance(
        employee,
        organization,
        work_date,
    )

    if attendance.check_in:
        return attendance

    if attendance.status in {"ON_LEAVE", "WEEKLY_OFF", "HOLIDAY"}:
        return attendance

    attendance.status = "ABSENT"
    attendance.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    return attendance
