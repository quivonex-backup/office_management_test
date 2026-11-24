from rest_framework import serializers
from datetime import date
from django.db.models import Q
from django.utils import timezone
from datetime import date
from .services import get_attendance_settings

from .models import (
    AttendanceSettings,
    Shift,
    EmployeeShiftAssignment,
    AttendanceRecord,
    AttendancePunch,
    AttendanceCorrection,
    AttendanceDevice,
)


# =========================================================
# SHARED HELPERS
# =========================================================

def get_employee_full_name(employee):
    parts = [
        employee.first_name,
        employee.middle_name,
        employee.last_name,
    ]
    return " ".join(part for part in parts if part)


# =========================================================
# ATTENDANCE SETTINGS
# =========================================================

class AttendanceSettingsSerializer(serializers.ModelSerializer):

    class Meta:
        model = AttendanceSettings
        fields = [
            "id",
            "organization",
            "photo_required",
            "location_required",
            "allowed_radius_meters",
            "max_gps_accuracy_meters",
            "face_match_threshold",
            "default_start_time",
            "default_end_time",
            "late_grace_minutes",
            "early_departure_grace_minutes",
            "half_day_threshold_minutes",
            "early_departure_half_day_threshold_minutes",
            "late_half_day_threshold_minutes",
            "overtime_minimum_minutes",
            "overtime_include_threshold",
            "auto_mark_absent",
            "absent_after_minutes",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]


# =========================================================
# SHIFT
# =========================================================

class ShiftSerializer(serializers.ModelSerializer):

    class Meta:
        model = Shift
        fields = [
            "id",
            "organization",
            "name",
            "start_time",
            "end_time",
            "crosses_midnight",
            "late_grace_minutes",
            "early_departure_grace_minutes",
            "is_active",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        start_time = attrs.get(
            "start_time",
            getattr(self.instance, "start_time", None),
        )
        end_time = attrs.get(
            "end_time",
            getattr(self.instance, "end_time", None),
        )
        crosses_midnight = attrs.get(
            "crosses_midnight",
            getattr(self.instance, "crosses_midnight", False),
        )

        if start_time and end_time:
            if start_time == end_time:
                raise serializers.ValidationError({
                    "end_time": "Start and end times cannot be identical."
                })

            if end_time < start_time and not crosses_midnight:
                raise serializers.ValidationError({
                    "crosses_midnight": (
                        "Enable this for a shift ending the next day."
                    )
                })

            if end_time > start_time and crosses_midnight:
                raise serializers.ValidationError({
                    "crosses_midnight": (
                        "Disable this for a shift ending on the same day."
                    )
                })

        return attrs


# =========================================================
# EMPLOYEE SHIFT ASSIGNMENT
# =========================================================

class EmployeeShiftAssignmentSerializer(serializers.ModelSerializer):

    employee_name = serializers.SerializerMethodField()
    employee_code = serializers.CharField(
        source="employee.employee_code",
        read_only=True,
    )
    shift_name = serializers.CharField(
        source="shift.name",
        read_only=True,
    )

    class Meta:
        model = EmployeeShiftAssignment
        fields = [
            "id",
            "organization",
            "employee",
            "employee_code",
            "employee_name",
            "shift",
            "shift_name",
            "effective_from",
            "effective_to",
            "assigned_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "assigned_by",
            "created_at",
            "updated_at",
        ]

    def get_employee_name(self, obj):
        return get_employee_full_name(obj.employee)

    def validate(self, attrs):
        employee = attrs.get(
            "employee",
            getattr(self.instance, "employee", None),
        )
        shift = attrs.get(
            "shift",
            getattr(self.instance, "shift", None),
        )
        effective_from = attrs.get(
            "effective_from",
            getattr(self.instance, "effective_from", None),
        )
        effective_to = attrs.get(
            "effective_to",
            getattr(self.instance, "effective_to", None),
        )

        organization = self.context.get("organization")

        if organization is None and self.instance:
            organization = self.instance.organization

        if organization is None:
            raise serializers.ValidationError(
                "Organization context is required."
            )

        # Validate employee and shift status.
        if employee:
            if employee.organization_id != organization.id:
                raise serializers.ValidationError({
                    "employee": "Employee does not belong to this organization."
                })

            if not employee.is_active or employee.employment_status != "ACTIVE":
                raise serializers.ValidationError({
                    "employee": "Only active employees can be assigned shifts."
                })

        if shift:
            if shift.organization_id != organization.id:
                raise serializers.ValidationError({
                    "shift": "Shift does not belong to this organization."
                })

            if not shift.is_active:
                raise serializers.ValidationError({
                    "shift": "Cannot assign an inactive shift."
                })

        if effective_from and effective_to and effective_to < effective_from:
            raise serializers.ValidationError({
                "effective_to": "End date cannot be before start date."
            })

        # Prevent overlapping assignments for the same employee.
        if employee and effective_from:
            overlapping = EmployeeShiftAssignment.objects.filter(
                organization=organization,
                employee=employee,
                effective_from__lte=effective_to or date.max,
            ).filter(
                Q(effective_to__isnull=True)
                | Q(effective_to__gte=effective_from)
            )

            # Important: only exclude an existing row when updating.
            # Do not use exclude(pk=None) on create.
            if self.instance:
                overlapping = overlapping.exclude(pk=self.instance.pk)

            conflict = overlapping.select_related("shift").first()

            if conflict:
                raise serializers.ValidationError({
                    "employee": (
                        f"Employee already has a shift assignment for "
                        f"'{conflict.shift.name}' from "
                        f"{conflict.effective_from} to "
                        f"{conflict.effective_to or 'open-ended'}. "
                        "Assignment date ranges cannot overlap."
                    )
                })

        return attrs


# =========================================================
# ATTENDANCE PUNCH
# =========================================================

class AttendancePunchSerializer(serializers.ModelSerializer):

    class Meta:
        model = AttendancePunch
        fields = [
            "id",
            "attendance",
            "punch_type",
            "punched_at",
            "latitude",
            "longitude",
            "gps_accuracy_meters",
            "office_distance_meters",
            "location_verified",
            "selfie",
            "face_similarity",
            "face_verified",
            "verification_status",
            "verification_details",
            "recorded_by",
            "is_manual",
            "created_at",
        ]
        read_only_fields = fields


# =========================================================
# EMPLOYEE CHECK-IN / CHECK-OUT REQUEST
# =========================================================


class AttendancePunchRequestSerializer(serializers.Serializer):

    latitude = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
        required=False,
        allow_null=True,
    )

    longitude = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
        required=False,
        allow_null=True,
    )

    gps_accuracy_meters = serializers.FloatField(
        required=False,
        allow_null=True,
        min_value=0,
    )

    selfie = serializers.ImageField(
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):

        organization = self.context.get("organization")

        attendance_settings = (
            AttendanceSettings.objects.filter(
                organization=organization
            ).first()
            if organization
            else None
        )

        # Default to requiring location if settings do not exist.
        location_required = (
            attendance_settings.location_required
            if attendance_settings
            else True
        )

        latitude = attrs.get("latitude")
        longitude = attrs.get("longitude")

        if location_required:
            if latitude is None or longitude is None:
                raise serializers.ValidationError({
                    "location": (
                        "Both latitude and longitude are required "
                        "because location verification is enabled."
                    )
                })

        # Validate any coordinates that were supplied.
        if latitude is not None and not -90 <= latitude <= 90:
            raise serializers.ValidationError({
                "latitude": "Latitude must be between -90 and 90."
            })

        if longitude is not None and not -180 <= longitude <= 180:
            raise serializers.ValidationError({
                "longitude": "Longitude must be between -180 and 180."
            })

        return attrs


# =========================================================
# ATTENDANCE RECORD
# =========================================================

class AttendanceRecordSerializer(serializers.ModelSerializer):

    employee_name = serializers.SerializerMethodField()
    employee_code = serializers.CharField(
        source="employee.employee_code",
        read_only=True,
    )
    shift_name = serializers.CharField(
        source="shift.name",
        read_only=True,
        allow_null=True,
    )
    punches = AttendancePunchSerializer(many=True, read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            "id",
            "organization",
            "employee",
            "employee_code",
            "employee_name",
            "shift",
            "shift_name",
            "work_date",
            "scheduled_start",
            "scheduled_end",
            "late_grace_minutes",
            "early_departure_grace_minutes",
            "check_in",
            "check_out",
            "net_work_minutes",
            "overtime_minutes",
            "late_minutes",
            "early_departure_minutes",
            "status",
            "punches",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_employee_name(self, obj):
        return get_employee_full_name(obj.employee)


# =========================================================
# ATTENDANCE CORRECTION
# =========================================================

class AttendanceCorrectionSerializer(serializers.ModelSerializer):

    employee_name = serializers.SerializerMethodField()
    employee_code = serializers.CharField(
        source="attendance.employee.employee_code",
        read_only=True,
    )
    work_date = serializers.DateField(
        source="attendance.work_date",
        read_only=True,
    )

    class Meta:
        model = AttendanceCorrection
        fields = [
            "id",
            "attendance",
            "work_date",
            "employee_code",
            "employee_name",
            "punch",
            "field_name",
            "old_value",
            "new_value",
            "reason",
            "status",
            "requested_by",
            "reviewed_by",
            "reviewed_at",
            "review_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "work_date",
            "employee_code",
            "employee_name",
            "old_value",
            "status",
            "requested_by",
            "reviewed_by",
            "reviewed_at",
            "review_note",
            "created_at",
            "updated_at",
        ]

    def get_employee_name(self, obj):
        return get_employee_full_name(obj.attendance.employee)

    def validate(self, attrs):
        attendance = attrs.get(
            "attendance",
            getattr(self.instance, "attendance", None),
        )
        punch = attrs.get(
            "punch",
            getattr(self.instance, "punch", None),
        )

        organization = self.context.get("organization")

        if organization is None and self.instance:
            organization = self.instance.attendance.organization

        if organization is None:
            raise serializers.ValidationError(
                "Organization context is required."
            )

        if attendance and attendance.organization_id != organization.id:
            raise serializers.ValidationError({
                "attendance": (
                    "Attendance record does not belong to this organization."
                )
            })

        if punch and attendance and punch.attendance_id != attendance.id:
            raise serializers.ValidationError({
                "punch": (
                    "The selected punch does not belong to this attendance record."
                )
            })

        return attrs


# =========================================================
# MY SHIFT ASSIGNMENT SERIALIZER (EMPLOYEE)
# =========================================================
class MyShiftAssignmentSerializer(serializers.ModelSerializer):

    assignment_id = serializers.IntegerField(source="id", read_only=True)
    shift_id = serializers.IntegerField(source="shift.id", read_only=True)
    shift_name = serializers.CharField(source="shift.name", read_only=True)
    start_time = serializers.TimeField(source="shift.start_time", read_only=True)
    end_time = serializers.TimeField(source="shift.end_time", read_only=True)
    crosses_midnight = serializers.BooleanField(source="shift.crosses_midnight", read_only=True)

    late_grace_minutes = serializers.SerializerMethodField()
    early_departure_grace_minutes = serializers.SerializerMethodField()
    is_current = serializers.SerializerMethodField()
    is_future = serializers.SerializerMethodField()
    is_past = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeShiftAssignment
        fields = [
            "assignment_id",
            "shift_id",
            "shift_name",
            "start_time",
            "end_time",
            "crosses_midnight",
            "late_grace_minutes",
            "early_departure_grace_minutes",
            "effective_from",
            "effective_to",
            "is_current",
            "is_future",
            "is_past",
        ]

    def _attendance_settings(self):
        return self.context.get("attendance_settings")

    def get_late_grace_minutes(self, obj):
        if obj.shift.late_grace_minutes is not None:
            return obj.shift.late_grace_minutes
        settings = self._attendance_settings()
        return settings.late_grace_minutes if settings else 0

    def get_early_departure_grace_minutes(self, obj):
        if obj.shift.early_departure_grace_minutes is not None:
            return obj.shift.early_departure_grace_minutes
        settings = self._attendance_settings()
        return settings.early_departure_grace_minutes if settings else 0

    def _today(self):
        # return date.today()
        return timezone.localdate()

    def get_is_past(self, obj):
        today = self._today()
        return obj.effective_to is not None and obj.effective_to < today

    def get_is_future(self, obj):
        return obj.effective_from > self._today()

    def get_is_current(self, obj):
        today = self._today()
        return (
            obj.effective_from <= today
            and (obj.effective_to is None or obj.effective_to >= today)
        )
    

# =========================================================
# ATTENDANCE DEVICES (kiosk)
# =========================================================

class AttendanceDeviceSerializer(serializers.ModelSerializer):
    """Device managers see everything, including the plain password."""

    branch = serializers.SerializerMethodField()
    logged_in = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceDevice
        fields = [
            "id", "name", "device_code", "password", "branch", "notes", "is_active",
            "logged_in", "token_issued_at", "locked_until", "last_login_at", "last_seen_at", "last_ip",
            "created_at", "updated_at",
        ]

    def get_branch(self, obj):
        return {"id": obj.branch_id, "name": obj.branch.name} if obj.branch else None

    def get_logged_in(self, obj):
        return bool(obj.token_hash)


class AttendanceDeviceWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    device_code = serializers.RegexField(
        r"^[A-Za-z0-9_-]{3,50}$", required=False, allow_blank=True, allow_null=True,
        error_messages={"invalid": "Use 3-50 letters, digits, '-' or '_'."},
    )
    branch_id = serializers.IntegerField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class KioskLoginSerializer(serializers.Serializer):
    device_code = serializers.CharField(max_length=50)
    password = serializers.CharField(max_length=50)


class KioskPunchRequestSerializer(AttendancePunchRequestSerializer):
    """Same fields and checks as the mobile punch + who / which button."""

    punch_type = serializers.ChoiceField(choices=["CHECK_IN", "CHECK_OUT"])
    employee_code = serializers.CharField(max_length=50)
