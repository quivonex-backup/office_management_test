from datetime import date, datetime

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
from common.permissions import (
    RequiredPermsMixin, has_perm, resolve_scope, own_request_denied, out_of_scope_denied,
    get_approver_users,
)
from app.audit.services import log_activity

from app.employees.models import Employee

from .models import (
    AttendanceSettings,
    Shift,
    EmployeeShiftAssignment,
    AttendanceRecord,
    AttendancePunch,
    AttendanceCorrection,
    AttendanceDevice,
)

from .serializers import (
    AttendanceSettingsSerializer,
    ShiftSerializer,
    EmployeeShiftAssignmentSerializer,
    AttendancePunchSerializer,
    AttendancePunchRequestSerializer,
    AttendanceRecordSerializer,
    AttendanceCorrectionSerializer,
    MyShiftAssignmentSerializer,
    AttendanceDeviceSerializer,
    AttendanceDeviceWriteSerializer,
    KioskLoginSerializer,
    KioskPunchRequestSerializer,
)
from .services import create_missed_day_request, withdraw_attendance_correction

from .services import (
    get_attendance_settings,
    get_employee_for_user,
    get_employee_for_organization,
    process_attendance_punch,
    create_attendance_correction,
    review_attendance_correction,
    bulk_assign_shift,
    bulk_assign_shift_pattern,
    bulk_mark_absent,
    calculate_attendance,
)
from .face_recognition_service import (
    FaceVerificationError,
    verify_employee_face,
)
from app.communications.notification_service import notify


# =========================================================
# SHARED HELPERS
# =========================================================

class AttendanceBaseAPIView(RequiredPermsMixin, APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_organization(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return None, error_response

        return organization, None

    def success(self, message, data=None, http_status=status.HTTP_200_OK, extra=None):
        response_data = {
            "status": True,
            "message": message,
        }

        if data is not None:
            response_data["data"] = data

        if extra:
            response_data.update(extra)

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

    def audit(self, **kwargs):
        try:
            log_activity(**kwargs)
        except Exception:
            pass

    def attendance_scope(self, request, organization, requested=None):
        """self | team | all for attendance data (batch 2)."""
        return resolve_scope(
            request, organization, requested,
            self_code="attendance.view_self",
            team_code="attendance.view_team",
            all_code="attendance.view_all",
        )


# =========================================================
# ATTENDANCE SETTINGS
# =========================================================

class AttendanceSettingsAPIView(AttendanceBaseAPIView):
    required_perms = ("settings.manage",)

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
    required_perms = ("settings.manage", "attendance.view_all", "attendance.view_team", "attendance.correct")

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
    required_perms = ("settings.manage",)

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

        self.audit(
            request=request,
            action="CREATE",
            module="ATTENDANCE",
            object_type="Shift",
            object_id=shift.id,
            description=f"Shift created: {shift.name}.",
            new_data=ShiftSerializer(shift).data,
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
    required_perms = ("settings.manage",)

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

        old_data = ShiftSerializer(shift).data

        serializer.save()

        self.audit(
            request=request,
            action="UPDATE",
            module="ATTENDANCE",
            object_type="Shift",
            object_id=shift.id,
            description=f"Shift updated: {shift.name}.",
            old_data=old_data,
            new_data=serializer.data,
        )

        return self.success(
            "Shift updated successfully.",
            serializer.data,
        )


# =========================================================
# SHIFT DEACTIVATE
# =========================================================

class ShiftDeactivateAPIView(AttendanceBaseAPIView):
    required_perms = ("settings.manage",)

    def post(self, request):
        organization, error_response = self.get_organization(request)
        if error_response:
            return error_response

        shift_id = request.data.get("shift_id")
        if not shift_id:
            return self.failure("shift_id is required.")

        shift = get_object_or_404(
            Shift, id=shift_id, organization=organization,
        )

        today = timezone.localdate()

        # --- GUARD: block if the shift still has an active/future assignment ---
        blocking = (
            EmployeeShiftAssignment.objects
            .filter(
                organization=organization,
                shift=shift,
            )
            .filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=today)
            )
            .select_related("employee")
            .order_by("employee_id")
        )

        blocking_list = list(blocking)
        if blocking_list:
            names = ", ".join(
                f"{a.employee.employee_code} "
                f"({a.effective_from} → {a.effective_to or 'open'})"
                for a in blocking_list[:5]
            )
            more = "" if len(blocking_list) <= 5 else f" and {len(blocking_list) - 5} more"
            return self.failure(
                f"Cannot deactivate shift '{shift.name}': "
                f"{len(blocking_list)} employee(s) still assigned — "
                f"{names}{more}. Reassign or close those assignments first."
            )

        shift.is_active = False
        shift.save(update_fields=["is_active", "updated_at"])

        self.audit(
            request=request,
            action="UPDATE",
            module="ATTENDANCE",
            object_type="Shift",
            object_id=shift.id,
            description=f"Shift deactivated: {shift.name}.",
            new_data={"is_active": False},
        )

        return self.success("Shift deactivated successfully.")


# =========================================================
# EMPLOYEE SHIFT ASSIGNMENT LIST
# =========================================================

class EmployeeShiftAssignmentListAPIView(AttendanceBaseAPIView):
    required_perms = ("settings.manage", "attendance.view_all", "attendance.view_team", "attendance.correct")

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
    required_perms = ("settings.manage",)

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

        self.audit(
            request=request,
            action="CREATE",
            module="ATTENDANCE",
            object_type="EmployeeShiftAssignment",
            object_id=assignment.id,
            description=(
                f"Shift '{assignment.shift.name}' assigned to "
                f"employee {assignment.employee.employee_code}."
            ),
            new_data=EmployeeShiftAssignmentSerializer(
                assignment, context={"organization": organization},
            ).data,
        )

        # ---- Notify employee of shift assignment ----
        if assignment.employee.user_id:
            transaction.on_commit(lambda: notify(
                users=assignment.employee.user,
                event_code="ATTENDANCE_SHIFT_ASSIGNED",
                title="New shift assigned",
                body=(
                    f"You have been assigned to '{assignment.shift.name}' "
                    f"starting {assignment.effective_from}."
                ),
                reference_type="employee_shift_assignment",
                reference_id=assignment.id,
                priority="NORMAL",
            ))

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
    required_perms = ("settings.manage",)

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

        old_data = EmployeeShiftAssignmentSerializer(
            assignment, context={"organization": organization},
        ).data

        assignment = serializer.save()

        self.audit(
            request=request,
            action="UPDATE",
            module="ATTENDANCE",
            object_type="EmployeeShiftAssignment",
            object_id=assignment.id,
            description=(
                f"Shift assignment updated for "
                f"employee {assignment.employee.employee_code}."
            ),
            old_data=old_data,
            new_data=EmployeeShiftAssignmentSerializer(
                assignment, context={"organization": organization},
            ).data,
        )

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
    required_perms = ("settings.manage",)

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

        self.audit(
            request=request,
            action="CREATE",
            module="ATTENDANCE",
            object_type="EmployeeShiftAssignment",
            object_id=None,
            description=(
                f"Bulk shift assign: {len(assignments)} employee(s) "
                f"to shift id {shift_id}."
            ),
            new_data={
                "created_count": len(assignments),
                "shift_id": shift_id,
                "effective_from": str(effective_from),
                "effective_to": (
                    str(effective_to) if effective_to else None
                ),
            },
        )

        # ---- Notify each employee of shift assignment ----
        recipient_users = []
        for a in assignments:
            if a.employee.user_id:
                recipient_users.append(a.employee.user)

        if recipient_users:
            transaction.on_commit(lambda: notify(
                users=recipient_users,
                event_code="ATTENDANCE_SHIFT_ASSIGNED",
                title="New shift assigned",
                body=(
                    f"You have been assigned to a new shift "
                    f"starting {effective_from}."
                ),
                reference_type="employee_shift_assignment_bulk",
                reference_id=None,
                priority="NORMAL",
            ))

        return self.success(
            "Shift assigned to employees successfully.",
            serializer.data,
            status.HTTP_201_CREATED,
        )


# =========================================================
# BULK ASSIGN A ROTATING SHIFT PATTERN
# =========================================================

class EmployeeShiftAssignmentPatternAPIView(AttendanceBaseAPIView):
    required_perms = ("settings.manage",)

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

        self.audit(
            request=request,
            action="CREATE",
            module="ATTENDANCE",
            object_type="EmployeeShiftAssignment",
            object_id=None,
            description=(
                f"Bulk rotating shift pattern assigned: "
                f"{len(assignments)} assignment(s)."
            ),
            new_data={
                "created_count": len(assignments),
                "start_date": str(start_date),
                "repetitions": repetitions,
                "pattern": pattern,
            },
        )

        # ---- Notify each employee of rotating shift pattern ----
        recipient_users = []
        for a in assignments:
            if a.employee.user_id:
                recipient_users.append(a.employee.user)

        if recipient_users:
            transaction.on_commit(lambda: notify(
                users=recipient_users,
                event_code="ATTENDANCE_SHIFT_ASSIGNED",
                title="New shift pattern assigned",
                body=(
                    f"You have been assigned a rotating shift pattern "
                    f"starting {start_date}."
                ),
                reference_type="employee_shift_assignment_pattern",
                reference_id=None,
                priority="NORMAL",
            ))

        return self.success(
            "Rotating shift pattern assigned successfully.",
            serializer.data,
            status.HTTP_201_CREATED,
        )


# =========================================================
# BULK CLOSE SHIFT ASSIGNMENTS
# =========================================================

class EmployeeShiftAssignmentBulkCloseAPIView(AttendanceBaseAPIView):
    required_perms = ("settings.manage",)

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

        self.audit(
            request=request,
            action="UPDATE",
            module="ATTENDANCE",
            object_type="EmployeeShiftAssignment",
            object_id=None,
            description=(
                f"Bulk shift close: {len(assignments)} assignment(s) "
                f"closed as of {effective_to}."
            ),
            new_data={
                "closed_count": len(assignments),
                "effective_to": str(effective_to),
            },
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

        self.audit(
            request=request,
            action="CREATE",
            module="ATTENDANCE",
            object_type="AttendancePunch",
            object_id=punch.id,
            description=(
                f"{punch.punch_type} recorded for "
                f"employee {employee.employee_code} on "
                f"{attendance.work_date}."
            ),
            new_data={
                "punch_type": punch.punch_type,
                "punched_at": str(punch.punched_at),
                "attendance_id": attendance.id,
                "work_date": str(attendance.work_date),
            },
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

        scope, error_response = self.attendance_scope(
            request, organization, request.data.get("scope"),
        )

        if error_response:
            return error_response

        queryset = scope.filter(AttendanceRecord.objects.filter(
            organization=organization,
        ).select_related(
            "employee",
            "shift",
        ).prefetch_related("punches"))

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
            extra={"scope_applied": scope.scope},
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

        # Own record, or a record inside the caller's team / organization
        # scope (attendance.view_team / attendance.view_all).
        scope, _error = self.attendance_scope(request, organization)

        if scope is None or not scope.allows(attendance.employee_id):
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

        # Employees can only request corrections to their own attendance,
        # unless they hold attendance.correct (HR).
        if (
            employee
            and attendance.employee_id != employee.id
            and not has_perm(request, organization, "attendance.correct")
        ):
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

        self.audit(
            request=request,
            action="CREATE",
            module="ATTENDANCE",
            object_type="AttendanceCorrection",
            object_id=correction.id,
            description=(
                f"Correction submitted for "
                f"{attendance.employee.employee_code} on "
                f"{attendance.work_date} (field: {correction.field_name})."
            ),
            new_data={
                "field_name": correction.field_name,
                "new_value": correction.new_value,
                "attendance_id": attendance.id,
            },
        )

        # ---- Notify the people who can approve it (batch 4.2) ----
        approvers = get_approver_users(
            organization, attendance.employee, "attendance.approve_correction",
            team_code="attendance.view_team", all_code="attendance.view_all",
        )

        if approvers:
            transaction.on_commit(lambda: notify(
                users=approvers,
                event_code="ATTENDANCE_CORRECTION_SUBMITTED",
                title="Attendance correction request",
                body=(
                    f"{attendance.employee.employee_code} requested a "
                    f"correction for {attendance.work_date} "
                    f"(field: {correction.field_name})."
                ),
                reference_type="attendance_correction",
                reference_id=correction.id,
                priority="HIGH",
            ))

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

        # queryset = AttendanceCorrection.objects.filter(
        #     attendance__organization=organization,
        # ).select_related(
        #     "attendance",
        #     "attendance__employee",
        #     "punch",
        # )

        scope, error_response = self.attendance_scope(
            request, organization, request.data.get("scope"),
        )

        if error_response:
            return error_response

        queryset = AttendanceCorrection.objects.filter(
            attendance__organization=organization,
        ).exclude(
            status="APPLIED",
            reviewed_by__isnull=True,
        )
        queryset = scope.filter(queryset, "attendance__employee_id").select_related(
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
            extra={"scope_applied": scope.scope},
        )


# =========================================================
# REVIEW CORRECTION
# =========================================================

class AttendanceCorrectionReviewAPIView(AttendanceBaseAPIView):
    required_perms = ("attendance.approve_correction",)

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

        scope, error_response = self.attendance_scope(request, organization)

        if error_response:
            return error_response

        if scope.employee and correction.attendance.employee_id == scope.employee.id:
            return own_request_denied()

        if not scope.allows(correction.attendance.employee_id):
            return out_of_scope_denied()

        try:
            correction = review_attendance_correction(
                correction=correction,
                reviewed_by=request.user,
                approve=approve,
                review_note=review_note,
            )
        except ValueError as exc:
            return self.failure(str(exc))

        self.audit(
            request=request,
            action="UPDATE",
            module="ATTENDANCE",
            object_type="AttendanceCorrection",
            object_id=correction.id,
            description=(
                f"Correction {correction.id} "
                f"{'approved' if approve else 'rejected'} "
                f"(field: {correction.field_name})."
            ),
            old_data={"status": "PENDING"},
            new_data={
                "status": correction.status,
                "review_note": review_note,
            },
        )

        # ---- Notify employee of review outcome ----
        if correction.attendance.employee.user_id:
            if approve:
                notification_title = "Attendance correction approved"
                notification_body = (
                    f"Your correction for "
                    f"{correction.attendance.work_date} was approved."
                )
            else:
                notification_title = "Attendance correction rejected"
                notification_body = (
                    f"Your correction for "
                    f"{correction.attendance.work_date} was rejected."
                )
                if review_note:
                    notification_body += f" Reason: {review_note}"

            transaction.on_commit(lambda: notify(
                users=correction.attendance.employee.user,
                event_code="ATTENDANCE_CORRECTION_REVIEWED",
                title=notification_title,
                body=notification_body,
                reference_type="attendance_correction",
                reference_id=correction.id,
                priority="HIGH",
            ))

        data = AttendanceCorrectionSerializer(
            correction,
            context={"organization": organization},
        ).data
        paired_id = getattr(correction, "paired_correction_id", None)
        if paired_id:
            # Batch 14: missed-day request, the check-in / check-out pair
            # was reviewed together.
            data["paired_correction_id"] = paired_id

        return self.success("Correction reviewed successfully.", data)


# =========================================================
# BULK MARK ABSENT
# =========================================================

class AttendanceBulkMarkAbsentAPIView(AttendanceBaseAPIView):
    required_perms = ("attendance.correct",)

    @transaction.atomic
    def post(self, request):
        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        from_date_raw = request.data.get("from_date")
        to_date_raw = request.data.get("to_date")
        employee_ids = request.data.get("employee_ids")

        try:
            from_date = self.parse_date(from_date_raw, "from_date")
            to_date = self.parse_date(to_date_raw, "to_date")
        except ValueError as exc:
            return self.failure(str(exc))

        if from_date is None or to_date is None:
            return self.failure(
                "from_date and to_date are required (YYYY-MM-DD)."
            )

        if from_date > to_date:
            return self.failure(
                "from_date cannot be after to_date."
            )

        if employee_ids is not None:
            if not isinstance(employee_ids, list) or not employee_ids:
                return self.failure(
                    "employee_ids must be a non-empty list when provided."
                )

        try:
            result = bulk_mark_absent(
                organization=organization,
                from_date=from_date,
                to_date=to_date,
                employee_ids=employee_ids,
                marked_by=request.user,
            )
        except ValueError as exc:
            return self.failure(str(exc))
        except Exception:
            return self.failure(
                "Unable to bulk-mark absent attendance.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        self.audit(
            request=request,
            action="CREATE",
            module="ATTENDANCE",
            object_type="AttendanceRecord",
            object_id=None,
            description=(
                f"Bulk absent mark: {result['created_count']} created, "
                f"{result['skipped_existing']} existed, "
                f"{result['skipped_non_working']} non-working days."
            ),
            new_data={
                "from_date": str(from_date),
                "to_date": str(to_date),
                "created_count": result["created_count"],
                "employees_processed": result["employees_processed"],
            },
        )

        return self.success(
            (
                f"Bulk absent mark completed: "
                f"{result['created_count']} created, "
                f"{result['skipped_existing']} already existed, "
                f"{result['skipped_non_working']} non-working days."
            ),
            result,
            (
                status.HTTP_201_CREATED
                if result["created_count"] > 0
                else status.HTTP_200_OK
            ),
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

        self.audit(
            request=request,
            action="OTHER",
            module="ATTENDANCE",
            object_type="FaceVerification",
            object_id=employee.id,
            description=(
                f"Face verification success for "
                f"employee {employee.employee_code}."
            ),
            new_data={
                "similarity": round(result["similarity"], 4),
            },
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


# =========================================================
# MY ATTENDANCE DIRECT CORRECTION
# Employee can directly correct their own historical timings.
# =========================================================

class MyAttendanceCorrectionAPIView(AttendanceBaseAPIView):

    @transaction.atomic
    def post(self, request):

        organization, error_response = self.get_organization(request)

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

        attendance_id = request.data.get("attendance_id")
        check_in_value = request.data.get("check_in")
        check_out_value = request.data.get("check_out")
        reason = str(request.data.get("reason", "")).strip()

        if not attendance_id:
            return self.failure("attendance_id is required.")

        if check_in_value is None and check_out_value is None:
            return self.failure(
                "Provide check_in or check_out to correct attendance."
            )

        if not reason:
            return self.failure("Correction reason is required.")

        attendance = get_object_or_404(
            AttendanceRecord.objects.select_for_update(),
            id=attendance_id,
            organization=organization,
            employee=employee,
        )

        def parse_datetime(value, field_name):

            if value in (None, ""):
                return None

            try:
                parsed_value = datetime.fromisoformat(
                    str(value).replace("Z", "+00:00")
                )
            except (TypeError, ValueError):
                raise ValueError(
                    f"{field_name} must be a valid ISO 8601 datetime."
                )

            if timezone.is_naive(parsed_value):
                parsed_value = timezone.make_aware(
                    parsed_value,
                    timezone.get_current_timezone(),
                )

            return parsed_value

        try:
            new_check_in = (
                parse_datetime(check_in_value, "check_in")
                if check_in_value is not None
                else attendance.check_in
            )

            new_check_out = (
                parse_datetime(check_out_value, "check_out")
                if check_out_value is not None
                else attendance.check_out
            )

        except ValueError as exc:
            return self.failure(str(exc))

        if new_check_in and new_check_out:
            if new_check_out <= new_check_in:
                return self.failure(
                    "Check-out must be later than check-in."
                )

        corrections = []

        correction_values = [
            (
                "CHECK_IN",
                "check_in",
                attendance.check_in,
                new_check_in,
                check_in_value is not None,
            ),
            (
                "CHECK_OUT",
                "check_out",
                attendance.check_out,
                new_check_out,
                check_out_value is not None,
            ),
        ]

        for field_name, model_field, old_value, new_value, supplied in correction_values:

            if not supplied:
                continue

            if old_value == new_value:
                continue

            if new_value is None:
                return self.failure(
                    f"{model_field} cannot be cleared through this API."
                )

            # Save the correction history as immediately applied.
            correction = AttendanceCorrection.objects.create(
                attendance=attendance,
                field_name=field_name,
                old_value=old_value.isoformat() if old_value else None,
                new_value=new_value.isoformat(),
                reason=reason,
                status="APPLIED",
                requested_by=request.user,
            )

            # Keep the corresponding punch record synchronized.
            punch, _ = AttendancePunch.objects.update_or_create(
                attendance=attendance,
                punch_type=field_name,
                defaults={
                    "punched_at": new_value,
                    "recorded_by": request.user,
                    "is_manual": True,
                    "verification_status": "MANUAL",
                    "verification_details": {
                        "source": "employee_direct_correction",
                        "correction_id": correction.id,
                        "reason": reason,
                    },
                },
            )

            correction.punch = punch
            correction.save(update_fields=["punch", "updated_at"])

            setattr(attendance, model_field, new_value)

            corrections.append({
                "field": field_name,
                "old_value": old_value.isoformat() if old_value else None,
                "new_value": new_value.isoformat(),
                "correction_id": correction.id,
            })

        if not corrections:
            return self.failure(
                "No attendance changes were provided."
            )

        attendance.updated_by = request.user
        attendance.save()

        # Recalculate PRESENT / HALF_DAY using existing attendance rules.
        calculate_attendance(attendance)

        attendance.refresh_from_db()

        self.audit(
            organization=organization,
            user=request.user,
            action="UPDATE",
            module="ATTENDANCE",
            description=(
                f"Employee directly corrected attendance "
                f"for {attendance.work_date}."
            ),
        )

        return self.success(
            "Attendance corrected successfully.",
            {
                "attendance": AttendanceRecordSerializer(
                    attendance,
                    context={"request": request},
                ).data,
                "corrections": corrections,
            },
        )


# =========================================================
# MY SHIFT ASSIGNMENTS (EMPLOYEE)
# =========================================================
class MyShiftAssignmentListAPIView(AttendanceBaseAPIView):

    def post(self, request):
        organization, error_response = self.get_organization(request)

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

        attendance_settings = get_attendance_settings(organization)
        today = timezone.localdate()

        include_inactive = request.data.get("include_inactive", False)

        if isinstance(include_inactive, str):
            include_inactive = (
                include_inactive.lower() in ("true", "1", "yes")
            )

        queryset = (
            EmployeeShiftAssignment.objects
            .filter(
                organization=organization,
                employee=employee,
            )
            .select_related("shift")
            .order_by("-effective_from")
        )

        if not include_inactive:
            queryset = queryset.filter(
                Q(effective_to__isnull=True)
                | Q(effective_to__gte=today)
            )

        date_from = request.data.get("date_from")
        date_to = request.data.get("date_to")

        try:
            if date_from:
                queryset = queryset.filter(
                    effective_from__gte=self.parse_date(
                        date_from,
                        "date_from",
                    )
                )

            if date_to:
                queryset = queryset.filter(
                    effective_from__lte=self.parse_date(
                        date_to,
                        "date_to",
                    )
                )

        except ValueError as exc:
            return self.failure(str(exc))

        assignments = list(queryset)

        context = {
            "request": request,
            "organization": organization,
            "attendance_settings": attendance_settings,
        }

        serializer = MyShiftAssignmentSerializer(
            assignments,
            many=True,
            context=context,
        )

        # Pick the single row that is active today, if any.
        current_row = next(
            (
                row for row in serializer.data
                if row["is_current"]
            ),
            None,
        )

        return self.success(
            "Your shift assignments fetched successfully.",
            {
                "employee_id": employee.id,
                "employee_code": employee.employee_code,
                "employee_name": (
                    f"{employee.first_name} "
                    f"{employee.middle_name or ''} "
                    f"{employee.last_name}"
                ).replace("  ", " ").strip(),
                "current_shift": current_row,
                "assignments": serializer.data,
            },
        )


# =========================================================
# =========================================================
# ATTENDANCE DEVICES (kiosk) — admin side
# perm: attendance.device_manage
# =========================================================
# =========================================================

import hashlib
import secrets
import string
from datetime import timedelta

KIOSK_MAX_FAILED_LOGINS = 5
KIOSK_LOCK_MINUTES = 15
_PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"   # no 0/O/1/l/I


def generate_device_password():
    """e.g. k8Rm-42Tx-9pQa (12 characters in 3 groups, easy to read and type)."""
    return "-".join("".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(4)) for _ in range(3))


def generate_device_code():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "KSK-" + "".join(secrets.choice(alphabet) for _ in range(6))
        if not AttendanceDevice.objects.filter(device_code=code).exists():
            return code


def hash_device_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return (request.META.get("REMOTE_ADDR") or "")[:45] or None


class AttendanceDeviceBaseAPIView(AttendanceBaseAPIView):
    required_perms = ("attendance.device_manage",)

    def get_device(self, request, organization, active_only=False):
        device_id = request.data.get("device_id")
        if not device_id:
            return None, self.failure("device_id is required.")
        qs = AttendanceDevice.objects.filter(pk=device_id, organization=organization).select_related("branch")
        if active_only:
            qs = qs.filter(is_active=True)
        device = qs.first()
        if device is None:
            return None, self.failure("Device not found.", status.HTTP_404_NOT_FOUND)
        return device, None

    def resolve_branch(self, organization, data):
        from app.accounts.models import Branch

        value = data.get("branch_id")
        if value in (None, "", "null"):
            return None, None
        branch = Branch.objects.filter(pk=value, organization=organization, is_active=True).first()
        if branch is None:
            return None, Response(
                {"status": False, "message": "Validation failed.",
                 "errors": {"branch_id": ["Active branch not found."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return branch, None

    def code_taken(self, code, exclude_id=None):
        qs = AttendanceDevice.objects.filter(device_code__iexact=code)
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)
        return qs.exists()

    def invalid(self, errors):
        return Response({"status": False, "message": "Validation failed.", "errors": errors},
                        status=status.HTTP_400_BAD_REQUEST)


# =========================================================
# DEVICE — CREATE
# =========================================================

class AttendanceDeviceCreateAPIView(AttendanceDeviceBaseAPIView):

    def post(self, request):
        organization, error_response = self.get_organization(request)
        if error_response:
            return error_response
        serializer = AttendanceDeviceWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return self.invalid(serializer.errors)
        data = serializer.validated_data

        branch, error_response = self.resolve_branch(organization, data)
        if error_response:
            return error_response
        code = (data.get("device_code") or "").strip().upper() or generate_device_code()
        if self.code_taken(code):
            return self.invalid({"device_code": ["This device code is already in use."]})

        device = AttendanceDevice.objects.create(
            organization=organization, branch=branch, name=data["name"].strip(), device_code=code,
            password=generate_device_password(), notes=(data.get("notes") or "").strip() or None,
            created_by=request.user, updated_by=request.user,
        )
        self.audit(
            request=request, action="CREATE", module="ATTENDANCE", object_type="AttendanceDevice",
            object_id=device.id, description=f"Attendance device {device.device_code} created.",
            new_data={"name": device.name, "device_code": device.device_code, "branch_id": device.branch_id},
        )
        return self.success("Device created.", AttendanceDeviceSerializer(device).data, status.HTTP_201_CREATED)


# =========================================================
# DEVICE — LIST (password included)
# =========================================================

class AttendanceDeviceListAPIView(AttendanceDeviceBaseAPIView):

    def post(self, request):
        organization, error_response = self.get_organization(request)
        if error_response:
            return error_response
        data = request.data
        qs = AttendanceDevice.objects.filter(organization=organization).select_related("branch")
        if str(data.get("include_inactive", "")).lower() not in ("true", "1", "yes"):
            qs = qs.filter(is_active=True)
        if data.get("branch_id"):
            qs = qs.filter(branch_id=data.get("branch_id"))
        search = (data.get("search") or "").strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(device_code__icontains=search))
        return self.success("Devices fetched.", AttendanceDeviceSerializer(qs.order_by("name"), many=True).data)


# =========================================================
# DEVICE — UPDATE
# =========================================================

class AttendanceDeviceUpdateAPIView(AttendanceDeviceBaseAPIView):

    def post(self, request):
        organization, error_response = self.get_organization(request)
        if error_response:
            return error_response
        device, error_response = self.get_device(request, organization)
        if error_response:
            return error_response
        serializer = AttendanceDeviceWriteSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return self.invalid(serializer.errors)
        data = serializer.validated_data
        old = AttendanceDeviceSerializer(device).data

        if "name" in data:
            device.name = data["name"].strip()
        if "notes" in data:
            device.notes = (data.get("notes") or "").strip() or None
        if "branch_id" in data:
            device.branch, error_response = self.resolve_branch(organization, data)
            if error_response:
                return error_response
        if data.get("device_code"):
            code = data["device_code"].strip().upper()
            if code != device.device_code:
                if self.code_taken(code, exclude_id=device.pk):
                    return self.invalid({"device_code": ["This device code is already in use."]})
                device.device_code = code
                device.token_hash = None          # the tablet must log in with the new code
                device.token_issued_at = None
        if str(request.data.get("is_active", "")).lower() in ("true", "1", "yes"):
            device.is_active = True
        device.updated_by = request.user
        device.save()
        self.audit(
            request=request, action="UPDATE", module="ATTENDANCE", object_type="AttendanceDevice",
            object_id=device.id, description=f"Attendance device {device.device_code} updated.",
            old_data={k: old[k] for k in ("name", "device_code", "branch", "notes", "is_active")},
            new_data={"name": device.name, "device_code": device.device_code, "branch_id": device.branch_id,
                      "is_active": device.is_active},
        )
        return self.success("Device updated.", AttendanceDeviceSerializer(device).data)


# =========================================================
# DEVICE — RESET PASSWORD (also logs the tablet out)
# =========================================================

class AttendanceDeviceResetPasswordAPIView(AttendanceDeviceBaseAPIView):

    def post(self, request):
        organization, error_response = self.get_organization(request)
        if error_response:
            return error_response
        device, error_response = self.get_device(request, organization)
        if error_response:
            return error_response
        device.password = generate_device_password()
        device.token_hash = None
        device.token_issued_at = None
        device.failed_logins = 0
        device.locked_until = None
        device.updated_by = request.user
        device.save()
        self.audit(
            request=request, action="UPDATE", module="ATTENDANCE", object_type="AttendanceDevice",
            object_id=device.id, description=f"Attendance device {device.device_code} password reset.",
        )
        return self.success("Password reset. The device must log in again.", AttendanceDeviceSerializer(device).data)


# =========================================================
# DEVICE — DEACTIVATE (logs the tablet out)
# =========================================================

class AttendanceDeviceDeactivateAPIView(AttendanceDeviceBaseAPIView):

    def post(self, request):
        organization, error_response = self.get_organization(request)
        if error_response:
            return error_response
        device, error_response = self.get_device(request, organization, active_only=True)
        if error_response:
            return error_response
        device.is_active = False
        device.token_hash = None
        device.token_issued_at = None
        device.updated_by = request.user
        device.save()
        self.audit(
            request=request, action="DELETE", module="ATTENDANCE", object_type="AttendanceDevice",
            object_id=device.id, description=f"Attendance device {device.device_code} deactivated.",
        )
        return self.success("Device deactivated.")


# =========================================================
# =========================================================
# KIOSK — no user login. Device token in "Authorization: Device <token>"
# =========================================================
# =========================================================

class KioskBaseAPIView(APIView):
    authentication_classes = []        # device token, not a user JWT
    permission_classes = []
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def fail(self, message, http_status=status.HTTP_400_BAD_REQUEST, errors=None):
        body = {"status": False, "message": message}
        if errors:
            body["errors"] = errors
        return Response(body, status=http_status)

    def get_device(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "device" or not token.strip():
            return None, self.fail("Device not logged in.", status.HTTP_401_UNAUTHORIZED)
        device = (
            AttendanceDevice.objects.filter(token_hash=hash_device_token(token.strip()))
            .select_related("organization", "branch").first()
        )
        if device is None:
            return None, self.fail("Device session ended. Log in again.", status.HTTP_401_UNAUTHORIZED)
        if not device.is_active or not getattr(device.organization, "is_active", True):
            return None, self.fail("Device is inactive.", status.HTTP_401_UNAUTHORIZED)
        return device, None


# =========================================================
# KIOSK — LOGIN
# =========================================================

class KioskLoginAPIView(KioskBaseAPIView):

    def post(self, request):
        serializer = KioskLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return self.fail("Validation failed.", errors=serializer.errors)
        code = serializer.validated_data["device_code"].strip()
        password = serializer.validated_data["password"]
        now = timezone.now()

        with transaction.atomic():
            device = (
                AttendanceDevice.objects.select_for_update()
                .filter(device_code__iexact=code).select_related("organization", "branch").first()
            )
            if device is None:
                return self.fail("Invalid device code or password.")
            if device.locked_until and device.locked_until > now:
                minutes = max(int((device.locked_until - now).total_seconds() // 60) + 1, 1)
                return self.fail(f"Too many attempts. Try again in {minutes} minutes.", status.HTTP_423_LOCKED)
            if not secrets.compare_digest(device.password, password):
                device.failed_logins += 1
                fields = ["failed_logins"]
                if device.failed_logins >= KIOSK_MAX_FAILED_LOGINS:
                    device.locked_until = now + timedelta(minutes=KIOSK_LOCK_MINUTES)
                    device.failed_logins = 0
                    fields.append("locked_until")
                device.save(update_fields=fields)
                return self.fail("Invalid device code or password.")
            if not device.is_active or not getattr(device.organization, "is_active", True):
                return self.fail("Device is inactive.", status.HTTP_403_FORBIDDEN)

            token = "dvc_" + secrets.token_urlsafe(36)
            device.token_hash = hash_device_token(token)
            device.token_issued_at = now
            device.failed_logins = 0
            device.locked_until = None
            device.last_login_at = now
            device.last_seen_at = now
            device.last_ip = client_ip(request)
            device.save(update_fields=["token_hash", "token_issued_at", "failed_logins", "locked_until",
                                       "last_login_at", "last_seen_at", "last_ip", "updated_at"])

        org = device.organization
        logo = None
        try:
            logo = org.logo.url if getattr(org, "logo", None) else None
        except Exception:
            logo = None
        return Response({
            "status": True,
            "message": "Device logged in.",
            "data": {
                "token": token,
                "device": {"id": device.id, "name": device.name, "device_code": device.device_code,
                           "branch": {"id": device.branch_id, "name": device.branch.name} if device.branch else None},
                "organization": {"id": org.id, "name": org.organization_name, "logo": logo},
            },
        }, status=status.HTTP_200_OK)


# =========================================================
# KIOSK — PUNCH (same rules as the mobile punch)
# =========================================================

class KioskPunchAPIView(KioskBaseAPIView):

    def post(self, request):
        device, error_response = self.get_device(request)
        if error_response:
            return error_response
        organization = device.organization

        serializer = KioskPunchRequestSerializer(data=request.data, context={"organization": organization})
        if not serializer.is_valid():
            return self.fail("Invalid attendance punch data.", errors=serializer.errors)
        data = serializer.validated_data

        employee = Employee.objects.filter(
            organization=organization, employee_code__iexact=data["employee_code"].strip(), is_active=True,
        ).first()
        if employee is None:
            return self.fail("Employee not found.", status.HTTP_404_NOT_FOUND)

        try:
            with transaction.atomic():     # a rejected punch leaves nothing behind
                attendance, punch = process_attendance_punch(
                    employee=employee,
                    organization=organization,
                    latitude=data.get("latitude"),
                    longitude=data.get("longitude"),
                    gps_accuracy_meters=data.get("gps_accuracy_meters"),
                    selfie_file=data.get("selfie"),
                    recorded_by=None,
                    expected_punch_type=data["punch_type"],
                    extra_details={"source": "KIOSK", "device_id": device.id, "device_name": device.name,
                                   "device_code": device.device_code},
                )
        except ValueError as exc:
            return self.fail(str(exc))
        except Exception:
            return self.fail("Unable to process attendance punch. Please try again.",
                             status.HTTP_500_INTERNAL_SERVER_ERROR)

        AttendanceDevice.objects.filter(pk=device.pk).update(last_seen_at=timezone.now(), last_ip=client_ip(request))
        try:
            log_activity(
                request=None, user=None, action="CREATE", module="ATTENDANCE", object_type="AttendancePunch",
                object_id=punch.id,
                description=(f"{punch.punch_type} recorded for employee {employee.employee_code} on "
                             f"{attendance.work_date} at kiosk {device.device_code}."),
                new_data={"punch_type": punch.punch_type, "punched_at": str(punch.punched_at),
                          "attendance_id": attendance.id, "device_id": device.id},
            )
        except Exception:
            pass

        try:
            photo = employee.profile_photo.url if employee.profile_photo else None
        except Exception:
            photo = None
        return Response({
            "status": True,
            "message": ("Check-in recorded successfully." if punch.punch_type == "CHECK_IN"
                        else "Check-out recorded successfully."),
            "data": {
                "employee": {"id": employee.id, "employee_code": employee.employee_code,
                             "name": " ".join(p for p in [employee.first_name, employee.last_name] if p),
                             "photo": photo},
                "punch": AttendancePunchSerializer(punch).data,
                "attendance": AttendanceRecordSerializer(attendance).data,
            },
        }, status=status.HTTP_201_CREATED)


# =========================================================
# =========================================================
# BATCH 14 — MISSED DAY REQUEST / WITHDRAW A PENDING CORRECTION
# =========================================================
# =========================================================

class AttendanceMissedDayRequestAPIView(AttendanceBaseAPIView):
    """
    Employee forgot to punch for a whole day (no check-in, no check-out).
    Creates two PENDING corrections (CHECK_IN + CHECK_OUT) reviewed together
    through corrections/review/. HR with attendance.correct may send
    employee_id for someone else.
    """

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response
        data = request.data

        own = get_employee_for_user(request.user, organization)
        employee = own
        if data.get("employee_id") and (own is None or str(data.get("employee_id")) != str(own.id)):
            if not has_perm(request, organization, "attendance.correct"):
                return self.failure("You can only request attendance for yourself.", status.HTTP_403_FORBIDDEN)
            employee = Employee.objects.filter(
                pk=data.get("employee_id"), organization=organization, is_active=True,
            ).first()
            if employee is None:
                return self.failure("Employee not found.", status.HTTP_404_NOT_FOUND)
        if employee is None:
            return self.failure("No active employee profile is linked to this user.", status.HTTP_404_NOT_FOUND)

        missing = [f for f in ("work_date", "check_in", "check_out", "reason") if not data.get(f)]
        if missing:
            return Response(
                {"status": False, "message": "Validation failed.",
                 "errors": {f: ["This field is required."] for f in missing}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            work_date = self.parse_date(data.get("work_date"), "work_date")
            attendance, corrections = create_missed_day_request(
                employee=employee, organization=organization, work_date=work_date,
                check_in=data.get("check_in"), check_out=data.get("check_out"),
                reason=data.get("reason"), requested_by=request.user,
            )
        except ValueError as exc:
            return self.failure(str(exc))

        self.audit(
            request=request, action="CREATE", module="ATTENDANCE", object_type="AttendanceCorrection",
            object_id=corrections[0].id,
            description=f"Missed-day attendance requested for {employee.employee_code} on {work_date}.",
            new_data={"attendance_id": attendance.id, "correction_ids": [c.id for c in corrections],
                      "check_in": corrections[0].new_value, "check_out": corrections[1].new_value},
        )

        approvers = get_approver_users(
            organization, employee, "attendance.approve_correction",
            team_code="attendance.view_team", all_code="attendance.view_all",
        )
        if approvers:
            first_id = corrections[0].id
            transaction.on_commit(lambda: notify(
                users=approvers,
                event_code="ATTENDANCE_CORRECTION_SUBMITTED",
                title="Missed-day attendance request",
                body=f"{employee.employee_code} requested attendance for {work_date} (no punches that day).",
                reference_type="attendance_correction",
                reference_id=first_id,
                priority="HIGH",
            ))

        return self.success(
            "Missed-day request submitted.",
            {
                "attendance_id": attendance.id,
                "work_date": str(work_date),
                "corrections": AttendanceCorrectionSerializer(
                    corrections, many=True, context={"organization": organization},
                ).data,
            },
            status.HTTP_201_CREATED,
        )


class AttendanceCorrectionCancelAPIView(AttendanceBaseAPIView):
    """Requester withdraws their own PENDING correction (missed-day pair together)."""

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response
        correction_id = request.data.get("correction_id")
        if not correction_id:
            return self.failure("correction_id is required.")
        correction = (
            AttendanceCorrection.objects.select_related("attendance__employee")
            .filter(pk=correction_id, attendance__organization=organization).first()
        )
        if correction is None:
            return self.failure("Correction not found.", status.HTTP_404_NOT_FOUND)
        if correction.requested_by_id != request.user.id:
            return self.failure("You can only withdraw your own requests.", status.HTTP_403_FORBIDDEN)

        employee_code = correction.attendance.employee.employee_code
        work_date = correction.attendance.work_date
        try:
            removed, record_removed = withdraw_attendance_correction(correction)
        except ValueError as exc:
            return self.failure(str(exc))

        self.audit(
            request=request, action="DELETE", module="ATTENDANCE", object_type="AttendanceCorrection",
            object_id=removed[0],
            description=f"Correction request(s) {removed} for {employee_code} on {work_date} withdrawn.",
            old_data={"correction_ids": removed, "attendance_record_removed": record_removed},
        )
        return self.success("Request withdrawn.", {"withdrawn_correction_ids": removed,
                                                    "attendance_record_removed": record_removed})


# =========================================================
# BATCH 16 — EMPLOYEE FILLS OWN MISSED DAY DIRECTLY
# (no approval, no notification; like my-attendance/correct)
# Self-contained: no other code uses this class. To remove it, delete this
# class and its line in urls.py (path + import); nothing else changes.
# =========================================================

class MyAttendanceMissedDayAPIView(AttendanceBaseAPIView):

    @staticmethod
    def _aware(value, field):
        if isinstance(value, datetime):
            parsed = value
        else:
            try:
                parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{field} must be an ISO 8601 datetime, e.g. 2026-11-20T09:30:00.") from exc
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    def _validate(self, employee, organization, work_date, check_in, check_out, reason):
        from datetime import timedelta

        if not reason or not str(reason).strip():
            raise ValueError("reason is required.")
        if work_date > timezone.localdate():
            raise ValueError("work_date cannot be in the future.")
        joining = getattr(employee, "joining_date", None)
        if joining and work_date < joining:
            raise ValueError("work_date is before the employee's joining date.")

        check_in = self._aware(check_in, "check_in")
        check_out = self._aware(check_out, "check_out")
        if timezone.localdate(check_in) != work_date:
            raise ValueError("check_in must be on work_date.")
        if check_out <= check_in:
            raise ValueError("check_out must be after check_in.")
        if timezone.localdate(check_out) > work_date + timedelta(days=1):
            raise ValueError("check_out can be at most the next day (overnight shift).")
        if check_out > timezone.now():
            raise ValueError("check_out cannot be in the future.")

        existing = (
            AttendanceRecord.objects.select_for_update()
            .filter(organization=organization, employee=employee, work_date=work_date).first()
        )
        if existing and (existing.check_in or existing.check_out):
            raise ValueError(
                "Attendance already has a check-in or check-out for this day. "
                "Use corrections/create/ to change it."
            )
        if existing and existing.corrections.filter(status="PENDING").exists():
            raise ValueError("A correction request for this day is already pending.")
        return existing, check_in, check_out

    def _apply(self, employee, organization, work_date, check_in, check_out, reason, user):
        from .services import calculate_attendance, get_or_create_attendance

        existing, check_in, check_out = self._validate(
            employee, organization, work_date, check_in, check_out, reason,
        )
        attendance = existing or get_or_create_attendance(employee, organization, work_date)
        reason = str(reason).strip()

        corrections = []
        for field, model_field, value in (("CHECK_IN", "check_in", check_in),
                                          ("CHECK_OUT", "check_out", check_out)):
            correction = AttendanceCorrection.objects.create(
                attendance=attendance, field_name=field, old_value=None, new_value=value.isoformat(),
                reason=reason, status="APPLIED", requested_by=user,
            )
            punch, _ = AttendancePunch.objects.update_or_create(
                attendance=attendance,
                punch_type=field,
                defaults={
                    "punched_at": value,
                    "recorded_by": user,
                    "is_manual": True,
                    "verification_status": "MANUAL",
                    "verification_details": {
                        "source": "employee_direct_missed_day",
                        "correction_id": correction.id,
                        "reason": reason,
                    },
                },
            )
            correction.punch = punch
            correction.save(update_fields=["punch", "updated_at"])
            setattr(attendance, model_field, value)
            corrections.append(correction)

        if attendance.status in ("ABSENT", "PENDING_REVIEW"):
            attendance.status = "INCOMPLETE"
        attendance.updated_by = user
        attendance.save()
        calculate_attendance(attendance)
        attendance.refresh_from_db()
        return attendance, corrections

    @transaction.atomic
    def post(self, request):
        organization, error_response = self.get_organization(request)
        if error_response:
            return error_response
        employee = get_employee_for_user(request.user, organization)
        if not employee:
            return self.failure("No active employee profile is linked to this user.", status.HTTP_404_NOT_FOUND)

        data = request.data
        missing = [f for f in ("work_date", "check_in", "check_out", "reason") if not data.get(f)]
        if missing:
            return Response(
                {"status": False, "message": "Validation failed.",
                 "errors": {f: ["This field is required."] for f in missing}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            work_date = self.parse_date(data.get("work_date"), "work_date")
            attendance, corrections = self._apply(
                employee, organization, work_date,
                data.get("check_in"), data.get("check_out"), data.get("reason"), request.user,
            )
        except ValueError as exc:
            return self.failure(str(exc))

        self.audit(
            request=request, user=request.user, action="UPDATE", module="ATTENDANCE",
            object_type="AttendanceRecord", object_id=attendance.id,
            description=f"Employee {employee.employee_code} directly filled missed day {work_date}.",
            new_data={"check_in": corrections[0].new_value, "check_out": corrections[1].new_value,
                      "correction_ids": [c.id for c in corrections]},
        )
        return self.success(
            "Attendance recorded successfully.",
            {
                "attendance": AttendanceRecordSerializer(attendance, context={"request": request}).data,
                "corrections": [
                    {"field": c.field_name, "old_value": None, "new_value": c.new_value, "correction_id": c.id}
                    for c in corrections
                ],
            },
        )

