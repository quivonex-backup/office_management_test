from datetime import date

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.parsers import (
    JSONParser,
    FormParser,
    MultiPartParser,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.services import get_user_organization

from app.employees.models import Employee

from .models import (
    AttendanceSettings,
    Shift,
    EmployeeShiftAssignment,
    AttendanceRecord,
    AttendancePunch,
    AttendanceCorrection,
)

from .serializers import (
    AttendanceSettingsSerializer,
    ShiftSerializer,
    EmployeeShiftAssignmentSerializer,
    AttendancePunchSerializer,
    AttendancePunchRequestSerializer,
    AttendanceRecordSerializer,
    AttendanceCorrectionSerializer,
)

from .services import (
    get_attendance_settings,
    get_employee_for_user,
    get_employee_for_organization,
    process_attendance_punch,
    create_attendance_correction,
    review_attendance_correction,
    bulk_assign_shift,
    bulk_assign_shift_pattern,
)
from .face_recognition_service import (
    FaceVerificationError,
    verify_employee_face,
)


# =========================================================
# SHARED HELPERS
# =========================================================

class AttendanceBaseAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_organization(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return None, error_response

        return organization, None

    def success(self, message, data=None, http_status=status.HTTP_200_OK):
        response_data = {
            "status": True,
            "message": message,
        }

        if data is not None:
            response_data["data"] = data

        return Response(response_data, status=http_status)

    def failure(self, message, http_status=status.HTTP_400_BAD_REQUEST):
        return Response(
            {
                "status": False,
                "message": message,
            },
            status=http_status,
        )

    def parse_date(self, value, field_name):
        if not value:
            return None

        try:
            return date.fromisoformat(str(value))
        except (TypeError, ValueError):
            raise ValueError(
                f"{field_name} must use YYYY-MM-DD format."
            )

    def get_scoped_attendance(self, organization, attendance_id):
        return get_object_or_404(
            AttendanceRecord,
            id=attendance_id,
            organization=organization,
        )


# =========================================================
# ATTENDANCE SETTINGS
# =========================================================

class AttendanceSettingsAPIView(AttendanceBaseAPIView):

    def post(self, request):
        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        settings_obj = get_attendance_settings(organization)

        serializer = AttendanceSettingsSerializer(
            settings_obj,
            data=request.data,
            partial=True,
            context={
                "request": request,
                "organization": organization,
            },
        )

        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Invalid attendance settings.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save(updated_by=request.user)

        return self.success(
            "Attendance settings retrieved/updated successfully.",
            serializer.data,
        )


# =========================================================
# SHIFT LIST
# =========================================================

class ShiftListAPIView(AttendanceBaseAPIView):

    def post(self, request):
        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        queryset = Shift.objects.filter(
            organization=organization,
        )

        is_active = request.data.get("is_active")

        if is_active is not None:
            if str(is_active).lower() in ("true", "1"):
                queryset = queryset.filter(is_active=True)
            elif str(is_active).lower() in ("false", "0"):
                queryset = queryset.filter(is_active=False)
            else:
                return self.failure(
                    "is_active must be true or false."
                )

        serializer = ShiftSerializer(queryset, many=True)

        return self.success(
            "Shifts fetched successfully.",
            serializer.data,
        )


# =========================================================
# SHIFT CREATE
# =========================================================

class ShiftCreateAPIView(AttendanceBaseAPIView):

    def post(self, request):
        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        serializer = ShiftSerializer(
            data=request.data,
            context={
                "request": request,
                "organization": organization,
            },
        )

        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Invalid shift data.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        shift = serializer.save(
            organization=organization,
            created_by=request.user,
        )

        return self.success(
            "Shift created successfully.",
            ShiftSerializer(shift).data,
            status.HTTP_201_CREATED,
        )


# =========================================================
# SHIFT UPDATE
# =========================================================

class ShiftUpdateAPIView(AttendanceBaseAPIView):

    def post(self, request):
        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        shift_id = request.data.get("shift_id")

        if not shift_id:
            return self.failure("shift_id is required.")

        shift = get_object_or_404(
            Shift,
            id=shift_id,
            organization=organization,
        )

        serializer = ShiftSerializer(
            shift,
            data=request.data,
            partial=True,
            context={
                "request": request,
                "organization": organization,
            },
        )

        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Invalid shift data.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()

        return self.success(
            "Shift updated successfully.",
            serializer.data,
        )


# =========================================================
# SHIFT DEACTIVATE
# =========================================================

class ShiftDeactivateAPIView(AttendanceBaseAPIView):

    def post(self, request):
        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        shift_id = request.data.get("shift_id")

        if not shift_id:
            return self.failure("shift_id is required.")

        shift = get_object_or_404(
            Shift,
            id=shift_id,
            organization=organization,
        )

        shift.is_active = False
        shift.save(update_fields=["is_active", "updated_at"])

        return self.success("Shift deactivated successfully.")


# =========================================================
# EMPLOYEE SHIFT ASSIGNMENT LIST
# =========================================================

class EmployeeShiftAssignmentListAPIView(AttendanceBaseAPIView):

    def post(self, request):
        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        queryset = EmployeeShiftAssignment.objects.filter(
            organization=organization,
        ).select_related("employee", "shift")

        employee_id = request.data.get("employee_id")
        shift_id = request.data.get("shift_id")
        effective_from = request.data.get("effective_from")

        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        if shift_id:
            queryset = queryset.filter(shift_id=shift_id)

        if effective_from:
            try:
                parsed_date = self.parse_date(
                    effective_from,
                    "effective_from",
                )
            except ValueError as exc:
                return self.failure(str(exc))

            queryset = queryset.filter(
                effective_from__lte=parsed_date,
            ).filter(
                models_q_assignment_active_on(parsed_date)
            )

        serializer = EmployeeShiftAssignmentSerializer(
            queryset,
            many=True,
            context={"organization": organization},
        )

        return self.success(
            "Shift assignments fetched successfully.",
            serializer.data,
        )


def models_q_assignment_active_on(target_date):
    from django.db.models import Q

    return Q(effective_to__isnull=True) | Q(
        effective_to__gte=target_date
    )


# =========================================================
# EMPLOYEE SHIFT ASSIGNMENT CREATE
# =========================================================

class EmployeeShiftAssignmentCreateAPIView(AttendanceBaseAPIView):

    def post(self, request):
        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        serializer = EmployeeShiftAssignmentSerializer(
            data=request.data,
            context={
                "request": request,
                "organization": organization,
            },
        )

        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Invalid shift assignment.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment = serializer.save(
            organization=organization,
            assigned_by=request.user,
        )

        return self.success(
            "Shift assigned successfully.",
            EmployeeShiftAssignmentSerializer(
                assignment,
                context={"organization": organization},
            ).data,
            status.HTTP_201_CREATED,
        )


# =========================================================
# EMPLOYEE SHIFT ASSIGNMENT UPDATE
# =========================================================

class EmployeeShiftAssignmentUpdateAPIView(AttendanceBaseAPIView):

    def post(self, request):
        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        assignment_id = request.data.get("assignment_id")

        if not assignment_id:
            return self.failure("assignment_id is required.")

        assignment = get_object_or_404(
            EmployeeShiftAssignment,
            id=assignment_id,
            organization=organization,
        )

        serializer = EmployeeShiftAssignmentSerializer(
            assignment,
            data=request.data,
            partial=True,
            context={
                "request": request,
                "organization": organization,
            },
        )

        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Invalid shift assignment.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        assignment = serializer.save()

        return self.success(
            "Shift assignment updated successfully.",
            EmployeeShiftAssignmentSerializer(
                assignment,
                context={"organization": organization},
            ).data,
        )


# =========================================================
# BULK ASSIGN ONE SHIFT TO MULTIPLE EMPLOYEES
# =========================================================

class EmployeeShiftAssignmentBulkAPIView(AttendanceBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        employee_ids = request.data.get("employee_ids")
        shift_id = request.data.get("shift_id")
        effective_from = request.data.get("effective_from")
        effective_to = request.data.get("effective_to")

        if not isinstance(employee_ids, list) or not employee_ids:
            return self.failure(
                "employee_ids must be a non-empty list."
            )

        if not shift_id:
            return self.failure("shift_id is required.")

        try:
            effective_from = self.parse_date(
                effective_from, "effective_from"
            )
            effective_to = (
                self.parse_date(effective_to, "effective_to")
                if effective_to else None
            )

            if not effective_from:
                return self.failure("effective_from is required.")

            assignments = bulk_assign_shift(
                organization=organization,
                employee_ids=employee_ids,
                shift_id=shift_id,
                effective_from=effective_from,
                effective_to=effective_to,
                assigned_by=request.user,
            )

        except ValueError as exc:
            return self.failure(str(exc))

        serializer = EmployeeShiftAssignmentSerializer(
            assignments,
            many=True,
            context={"organization": organization},
        )

        return self.success(
            "Shift assigned to employees successfully.",
            serializer.data,
            status.HTTP_201_CREATED,
        )


# =========================================================
# BULK ASSIGN A ROTATING SHIFT PATTERN
# =========================================================

class EmployeeShiftAssignmentPatternAPIView(AttendanceBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        employee_ids = request.data.get("employee_ids")
        start_date = request.data.get("start_date")
        pattern = request.data.get("pattern")
        repetitions = request.data.get("repetitions", 1)
        auto_close_prior = request.data.get("auto_close_prior", False)

        if not isinstance(employee_ids, list) or not employee_ids:
            return self.failure(
                "employee_ids must be a non-empty list."
            )

        if not isinstance(pattern, list) or not pattern:
            return self.failure(
                "pattern must be a non-empty list."
            )

        if not isinstance(auto_close_prior, bool):
            return self.failure(
                "auto_close_prior must be true or false."
            )

        try:
            start_date = self.parse_date(start_date, "start_date")

            if not start_date:
                return self.failure("start_date is required.")

            if isinstance(repetitions, bool):
                return self.failure(
                    "repetitions must be a positive integer."
                )

            repetitions = int(repetitions)

            assignments = bulk_assign_shift_pattern(
                organization=organization,
                employee_ids=employee_ids,
                start_date=start_date,
                pattern=pattern,
                repetitions=repetitions,
                assigned_by=request.user,
                auto_close_prior=auto_close_prior,
            )

        except (ValueError, TypeError) as exc:
            return self.failure(str(exc))

        serializer = EmployeeShiftAssignmentSerializer(
            assignments,
            many=True,
            context={"organization": organization},
        )

        return self.success(
            "Rotating shift pattern assigned successfully.",
            serializer.data,
            status.HTTP_201_CREATED,
        )


# =========================================================
# BULK CLOSE SHIFT ASSIGNMENTS
# =========================================================

class EmployeeShiftAssignmentBulkCloseAPIView(AttendanceBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        assignment_ids = request.data.get("assignment_ids")
        effective_to = request.data.get("effective_to")

        if not isinstance(assignment_ids, list) or not assignment_ids:
            return self.failure(
                "assignment_ids must be a non-empty list."
            )

        try:
            effective_to = self.parse_date(
                effective_to, "effective_to"
            )

            if not effective_to:
                return self.failure("effective_to is required.")

        except ValueError as exc:
            return self.failure(str(exc))

        assignments = list(
            EmployeeShiftAssignment.objects.filter(
                organization=organization,
                id__in=assignment_ids,
            ).select_related("employee", "shift")
        )

        if len(assignments) != len(set(assignment_ids)):
            return self.failure(
                "One or more assignment IDs were not found "
                "in this organization."
            )

        # Validate every assignment before updating any of them.
        for assignment in assignments:
            if effective_to < assignment.effective_from:
                return self.failure(
                    f"End date cannot be before the start date for "
                    f"assignment {assignment.id}."
                )

            # CHANGED: Closing an open-ended assignment must not overlap
            # another assignment belonging to the same employee.
            if assignment.effective_to is None:
                other_conflict = EmployeeShiftAssignment.objects.filter(
                    organization=organization,
                    employee=assignment.employee,
                    effective_from__lte=effective_to,
                ).filter(
                    Q(effective_to__isnull=True)
                    | Q(effective_to__gte=assignment.effective_from)
                ).exclude(
                    id=assignment.id
                ).first()

                if other_conflict:
                    return self.failure(
                        f"Cannot close assignment {assignment.id} to "
                        f"{effective_to}: it would overlap assignment "
                        f"{other_conflict.id}."
                    )

            if (
                assignment.effective_to is not None
                and effective_to > assignment.effective_to
            ):
                return self.failure(
                    f"Assignment {assignment.id} already ends on "
                    f"{assignment.effective_to}; it cannot be extended "
                    "by this close operation."
                )

            attendance_exists = AttendanceRecord.objects.filter(
                organization=organization,
                employee=assignment.employee,
                shift=assignment.shift,
                work_date__gt=effective_to,
            ).exists()

            if attendance_exists:
                return self.failure(
                    f"Cannot close assignment {assignment.id}: "
                    "attendance records already exist after the "
                    "requested end date for this employee and shift."
                )

        for assignment in assignments:
            assignment.effective_to = effective_to
            assignment.save(
                update_fields=["effective_to", "updated_at"]
            )

        serializer = EmployeeShiftAssignmentSerializer(
            assignments,
            many=True,
            context={"organization": organization},
        )

        return self.success(
            "Shift assignments closed successfully.",
            serializer.data,
        )


# =========================================================
# ATTENDANCE PUNCH
# Automatically checks in or checks out.
# organization_id is optional when the user has one
# active organization membership.
# =========================================================

class AttendancePunchAPIView(AttendanceBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        employee = get_employee_for_user(
            request.user,
            organization,
        )

        if not employee:
            return self.failure(
                "No active employee profile is linked to this user.",
                status.HTTP_404_NOT_FOUND,
            )

        serializer = AttendancePunchRequestSerializer(
            data=request.data,
            context={"organization": organization},
        )

        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Invalid attendance punch data.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            attendance, punch = process_attendance_punch(
                employee=employee,
                organization=organization,
                latitude=serializer.validated_data.get("latitude"),
                longitude=serializer.validated_data.get("longitude"),
                gps_accuracy_meters=(
                    serializer.validated_data.get(
                        "gps_accuracy_meters"
                    )
                ),
                selfie_file=serializer.validated_data.get("selfie"),
                recorded_by=request.user,
            )

        except ValueError as exc:
            return self.failure(str(exc))

        except Exception:
            # Log the exception in your production logging system.
            return self.failure(
                "Unable to process attendance punch. Please try again.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return self.success(
            (
                "Check-in recorded successfully."
                if punch.punch_type == "CHECK_IN"
                else "Check-out recorded successfully."
            ),
            {
                "punch": AttendancePunchSerializer(punch).data,
                "attendance": AttendanceRecordSerializer(
                    attendance
                ).data,
            },
            status.HTTP_201_CREATED,
        )


# =========================================================
# ATTENDANCE LIST
# Supports date, employee and status filters.
# =========================================================

class AttendanceListAPIView(AttendanceBaseAPIView):

    def post(self, request):
        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        queryset = AttendanceRecord.objects.filter(
            organization=organization,
        ).select_related(
            "employee",
            "shift",
        ).prefetch_related("punches")

        employee_id = request.data.get("employee_id")
        status_filter = request.data.get("status")
        work_date = request.data.get("work_date")
        from_date = request.data.get("from_date")
        to_date = request.data.get("to_date")

        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        try:
            if work_date:
                parsed_date = self.parse_date(work_date, "work_date")
                queryset = queryset.filter(work_date=parsed_date)

            if from_date:
                parsed_from = self.parse_date(from_date, "from_date")
                queryset = queryset.filter(work_date__gte=parsed_from)

            if to_date:
                parsed_to = self.parse_date(to_date, "to_date")
                queryset = queryset.filter(work_date__lte=parsed_to)

        except ValueError as exc:
            return self.failure(str(exc))

        if from_date and to_date and parsed_from > parsed_to:
            return self.failure(
                "from_date cannot be later than to_date."
            )

        serializer = AttendanceRecordSerializer(
            queryset,
            many=True,
        )

        return self.success(
            "Attendance records fetched successfully.",
            serializer.data,
        )


# =========================================================
# MY ATTENDANCE
# Returns attendance belonging to the logged-in employee.
# =========================================================

class MyAttendanceListAPIView(AttendanceBaseAPIView):

    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        employee = get_employee_for_user(
            request.user,
            organization,
        )

        if not employee:
            return self.failure(
                "No active employee profile is linked to this user.",
                status.HTTP_404_NOT_FOUND,
            )

        queryset = AttendanceRecord.objects.filter(
            organization=organization,
            employee=employee,
        ).select_related(
            "shift",
        ).prefetch_related(
            "punches",
        )

        try:
            work_date = request.data.get("work_date")
            from_date = request.data.get("from_date")
            to_date = request.data.get("to_date")

            if work_date:
                queryset = queryset.filter(
                    work_date=self.parse_date(
                        work_date,
                        "work_date",
                    )
                )

            if from_date:
                queryset = queryset.filter(
                    work_date__gte=self.parse_date(
                        from_date,
                        "from_date",
                    )
                )

            if to_date:
                queryset = queryset.filter(
                    work_date__lte=self.parse_date(
                        to_date,
                        "to_date",
                    )
                )

            if from_date and to_date:
                parsed_from = self.parse_date(
                    from_date,
                    "from_date",
                )
                parsed_to = self.parse_date(
                    to_date,
                    "to_date",
                )

                if parsed_from > parsed_to:
                    return self.failure(
                        "from_date cannot be later than to_date."
                    )

        except ValueError as exc:
            return self.failure(str(exc))

        serializer = AttendanceRecordSerializer(
            queryset,
            many=True,
        )

        return self.success(
            "Your attendance fetched successfully.",
            serializer.data,
        )


# =========================================================
# ATTENDANCE DETAIL
# Employees can view only their own attendance.
# Authorized organization managers can view organization records
# through the project's permission system.
# =========================================================

class AttendanceDetailAPIView(AttendanceBaseAPIView):

    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        attendance_id = request.data.get("attendance_id")

        if not attendance_id:
            return self.failure(
                "attendance_id is required.",
                status.HTTP_400_BAD_REQUEST,
            )

        attendance = get_object_or_404(
            AttendanceRecord.objects.select_related(
                "employee",
                "shift",
            ).prefetch_related(
                "punches",
            ),
            id=attendance_id,
            organization=organization,
        )

        employee = get_employee_for_user(
            request.user,
            organization,
        )

        # A linked employee must not access another employee's record.
        if employee and employee.id != attendance.employee_id:
            return self.failure(
                "You do not have permission to view this attendance record.",
                status.HTTP_403_FORBIDDEN,
            )

        return self.success(
            "Attendance details fetched successfully.",
            AttendanceRecordSerializer(attendance).data,
        )


# =========================================================
# CREATE ATTENDANCE CORRECTION
# Employees can request corrections to their own attendance.
# Authorized managers may use this endpoint for their
# organization, subject to the project's permission system.
# =========================================================

class AttendanceCorrectionCreateAPIView(AttendanceBaseAPIView):

    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        attendance_id = request.data.get("attendance")

        if not attendance_id:
            return self.failure(
                "attendance is required.",
                status.HTTP_400_BAD_REQUEST,
            )

        attendance = get_object_or_404(
            AttendanceRecord.objects.select_related("employee"),
            id=attendance_id,
            organization=organization,
        )

        employee = get_employee_for_user(
            request.user,
            organization,
        )

        # If this user is an employee, they can only request
        # corrections to their own attendance.
        if employee and attendance.employee_id != employee.id:
            return self.failure(
                "You can only request corrections to your own attendance.",
                status.HTTP_403_FORBIDDEN,
            )

        serializer = AttendanceCorrectionSerializer(
            data=request.data,
            context={
                "request": request,
                "organization": organization,
            },
        )

        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Invalid correction request.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Ensure the serializer resolved the same attendance record
        # that was validated against the organization above.
        validated_attendance = serializer.validated_data.get(
            "attendance"
        )

        if (
            validated_attendance is None
            or validated_attendance.id != attendance.id
        ):
            return self.failure(
                "Invalid attendance record.",
                status.HTTP_400_BAD_REQUEST,
            )

        try:
            correction = create_attendance_correction(
                attendance=attendance,
                field_name=serializer.validated_data["field_name"],
                new_value=serializer.validated_data["new_value"],
                reason=serializer.validated_data["reason"],
                requested_by=request.user,
                punch=serializer.validated_data.get("punch"),
            )

        except ValueError as exc:
            return self.failure(str(exc))

        return self.success(
            "Attendance correction submitted successfully.",
            AttendanceCorrectionSerializer(
                correction,
                context={
                    "organization": organization,
                },
            ).data,
            status.HTTP_201_CREATED,
        )


# =========================================================
# LIST CORRECTIONS BY DATE / EMPLOYEE / STATUS
# =========================================================

class AttendanceCorrectionListAPIView(AttendanceBaseAPIView):

    def post(self, request):
        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        queryset = AttendanceCorrection.objects.filter(
            attendance__organization=organization,
        ).select_related(
            "attendance",
            "attendance__employee",
            "punch",
        )

        employee_id = request.data.get("employee_id")
        correction_status = request.data.get("status")
        work_date = request.data.get("work_date")
        from_date = request.data.get("from_date")
        to_date = request.data.get("to_date")

        if employee_id:
            queryset = queryset.filter(
                attendance__employee_id=employee_id
            )

        if correction_status:
            queryset = queryset.filter(status=correction_status)

        try:
            if work_date:
                queryset = queryset.filter(
                    attendance__work_date=self.parse_date(
                        work_date,
                        "work_date",
                    )
                )

            if from_date:
                queryset = queryset.filter(
                    attendance__work_date__gte=self.parse_date(
                        from_date,
                        "from_date",
                    )
                )

            if to_date:
                queryset = queryset.filter(
                    attendance__work_date__lte=self.parse_date(
                        to_date,
                        "to_date",
                    )
                )

        except ValueError as exc:
            return self.failure(str(exc))

        serializer = AttendanceCorrectionSerializer(
            queryset,
            many=True,
            context={"organization": organization},
        )

        return self.success(
            "Attendance corrections fetched successfully.",
            serializer.data,
        )


# =========================================================
# REVIEW CORRECTION
# =========================================================

class AttendanceCorrectionReviewAPIView(AttendanceBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        correction_id = request.data.get("correction_id")
        approve = request.data.get("approve")
        review_note = request.data.get("review_note", "")

        if not correction_id:
            return self.failure("correction_id is required.")

        if not isinstance(approve, bool):
            return self.failure(
                "approve must be a boolean: true or false."
            )

        correction = get_object_or_404(
            AttendanceCorrection.objects.select_related(
                "attendance",
                "attendance__employee",
            ),
            id=correction_id,
            attendance__organization=organization,
        )

        try:
            correction = review_attendance_correction(
                correction=correction,
                reviewed_by=request.user,
                approve=approve,
                review_note=review_note,
            )
        except ValueError as exc:
            return self.failure(str(exc))

        return self.success(
            "Correction reviewed successfully.",
            AttendanceCorrectionSerializer(
                correction,
                context={"organization": organization},
            ).data,
        )



# =========================================================
# Face Verification
# =========================================================

class FaceRecognitionAPIView(AttendanceBaseAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        employee = get_employee_for_user(
            request.user,
            organization,
        )

        if not employee:
            return self.failure(
                "No active employee profile is linked to this user.",
                status.HTTP_404_NOT_FOUND,
            )

        selfie_file = request.FILES.get("selfie")

        if not selfie_file:
            return self.failure(
                "Upload a selfie using the 'selfie' field.",
                status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = verify_employee_face(
                employee=employee,
                selfie_file=selfie_file,
            )

        except FaceVerificationError as exc:
            return self.failure(
                str(exc),
                status.HTTP_400_BAD_REQUEST,
            )

        if not result["verified"]:
            return self.failure(
                "Face does not match your registered profile photo.",
                status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "status": True,
                "message": "Face recognized successfully.",
                "data": {
                    "verified": True,
                    "employee_code": employee.employee_code,
                    "similarity": round(
                        result["similarity"], 4
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )
