from rest_framework import serializers
from datetime import date
from django.db.models import Q

from .models import (
    AttendanceSettings,
    Shift,
    EmployeeShiftAssignment,
    AttendanceRecord,
    AttendancePunch,
    AttendanceCorrection,
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

        # --- existing org-scoped ownership checks ---
        if employee and employee.organization_id != organization.id:
            raise serializers.ValidationError({
                "employee": "Employee does not belong to this organization."
            })

        if shift and shift.organization_id != organization.id:
            raise serializers.ValidationError({
                "shift": "Shift does not belong to this organization."
            })

        # --- existing date-order check (kept for a friendly message) ---
        if effective_from and effective_to and effective_to < effective_from:
            raise serializers.ValidationError({
                "effective_to": "End date cannot be before start date."
            })

        # --- NEW: prevent overlapping assignments for the same employee ---
        if employee and effective_from:
            overlapping = (
                EmployeeShiftAssignment.objects.filter(
                    organization=organization,
                    employee=employee,
                )
                .exclude(pk=self.instance.pk if self.instance else None)
                .filter(
                    # existing.effective_from <= new.effective_to
                    # (treat NULL effective_to on the NEW side as "forever")
                    effective_from__lte=(
                        effective_to
                        if effective_to is not None
                        else date.max
                    ),
                )
                .filter(
                    # existing.effective_to IS NULL
                    # OR existing.effective_to >= new.effective_from
                    Q(effective_to__isnull=True)
                    | Q(effective_to__gte=effective_from)
                )
                .select_related("shift")
                .order_by("effective_from")
            )

            conflict = overlapping.first()

            if conflict is not None:
                if conflict.effective_to is None:
                    message = (
                        f"Employee already has an ongoing assignment to "
                        f"'{conflict.shift.name}' since "
                        f"{conflict.effective_from.isoformat()}. "
                        f"Set an end date on that assignment before "
                        f"creating a new one."
                    )
                else:
                    message = (
                        f"Employee already has an assignment to "
                        f"'{conflict.shift.name}' overlapping this period "
                        f"({conflict.effective_from.isoformat()} – "
                        f"{conflict.effective_to.isoformat()}). "
                        f"Shift date ranges must not overlap."
                    )

                raise serializers.ValidationError({"employee": message})

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
