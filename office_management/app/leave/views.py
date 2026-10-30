from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from common.services import get_user_organization

from app.employees.models import Employee

from .models import (
    LeaveType,
    EmployeeLeaveBalance,
    LeaveApplication,
    LeaveBalanceTransaction,
)

from .serializers import (
    LeaveTypeSerializer,
    EmployeeLeaveBalanceSerializer,
    LeaveApplicationSerializer,
    LeaveBalanceTransactionSerializer,
)

from .services import (
    initialize_leave_balances,
    create_leave_application,
    review_leave_application,
    cancel_leave_application,
    adjust_leave_balance,
)


# =========================================================
# BASE VIEW
# =========================================================

class LeaveBaseAPIView(APIView):

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get_organization(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return None, error_response

        return organization, None

    def success(
        self,
        message,
        data=None,
        http_status=status.HTTP_200_OK,
    ):
        response_data = {
            "status": True,
            "message": message,
        }

        if data is not None:
            response_data["data"] = data

        return Response(response_data, status=http_status)

    def failure(
        self,
        message,
        http_status=status.HTTP_400_BAD_REQUEST,
        errors=None,
    ):
        response_data = {
            "status": False,
            "message": message,
        }

        if errors is not None:
            response_data["errors"] = errors

        return Response(response_data, status=http_status)

    def get_employee(self, request, organization):
        return Employee.objects.filter(
            user=request.user,
            organization=organization,
            is_active=True,
            employment_status="ACTIVE",
        ).first()

    def parse_date(self, value, field_name):
        if not value:
            raise ValueError(f"{field_name} is required.")

        try:
            return date.fromisoformat(str(value))
        except (TypeError, ValueError):
            raise ValueError(
                f"{field_name} must use YYYY-MM-DD format."
            )


# =========================================================
# 1. LEAVE TYPE LIST
# Employee and organization users
# =========================================================

class LeaveTypeListAPIView(LeaveBaseAPIView):

    def post(self, request):

        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        queryset = LeaveType.objects.filter(
            organization=organization,
            is_active=True,
        )

        serializer = LeaveTypeSerializer(
            queryset,
            many=True,
        )

        return self.success(
            "Leave types fetched successfully.",
            serializer.data,
        )


# =========================================================
# 2. LEAVE TYPE CREATE
# =========================================================

class LeaveTypeCreateAPIView(LeaveBaseAPIView):

    def post(self, request):

        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        serializer = LeaveTypeSerializer(data=request.data)

        if not serializer.is_valid():
            return self.failure(
                "Invalid leave type data.",
                errors=serializer.errors,
            )

        try:
            leave_type = serializer.save(
                organization=organization,
            )
        except IntegrityError:
            return self.failure(
                "A leave type with this name or code already exists."
            )

        return self.success(
            "Leave type created successfully.",
            LeaveTypeSerializer(leave_type).data,
            status.HTTP_201_CREATED,
        )


# =========================================================
# 3. LEAVE TYPE UPDATE
# =========================================================

class LeaveTypeUpdateAPIView(LeaveBaseAPIView):

    def post(self, request):

        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        leave_type_id = request.data.get("leave_type_id")

        if not leave_type_id:
            return self.failure("leave_type_id is required.")

        leave_type = get_object_or_404(
            LeaveType,
            id=leave_type_id,
            organization=organization,
        )

        serializer = LeaveTypeSerializer(
            leave_type,
            data=request.data,
            partial=True,
        )

        if not serializer.is_valid():
            return self.failure(
                "Invalid leave type data.",
                errors=serializer.errors,
            )

        try:
            leave_type = serializer.save()
        except IntegrityError:
            return self.failure(
                "A leave type with this name or code already exists."
            )

        return self.success(
            "Leave type updated successfully.",
            LeaveTypeSerializer(leave_type).data,
        )


# =========================================================
# 4. LEAVE TYPE DEACTIVATE
# =========================================================

class LeaveTypeDeactivateAPIView(LeaveBaseAPIView):

    def post(self, request):

        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        leave_type_id = request.data.get("leave_type_id")

        if not leave_type_id:
            return self.failure("leave_type_id is required.")

        leave_type = get_object_or_404(
            LeaveType,
            id=leave_type_id,
            organization=organization,
        )

        if not leave_type.is_active:
            return self.failure("Leave type is already inactive.")

        leave_type.is_active = False
        leave_type.save(update_fields=["is_active", "updated_at"])

        return self.success(
            "Leave type deactivated successfully."
        )


# =========================================================
# 5. MY LEAVE BALANCES
# Employee only
# =========================================================

class MyLeaveBalanceListAPIView(LeaveBaseAPIView):

    def post(self, request):

        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        employee = self.get_employee(request, organization)

        if not employee:
            return self.failure(
                "No active employee profile is linked to this user.",
                status.HTTP_404_NOT_FOUND,
            )

        queryset = EmployeeLeaveBalance.objects.filter(
            organization=organization,
            employee=employee,
        ).select_related(
            "employee",
            "leave_type",
        )

        leave_year = request.data.get("leave_year")

        if leave_year:
            try:
                leave_year = int(leave_year)
            except (TypeError, ValueError):
                return self.failure("Invalid leave_year.")

            queryset = queryset.filter(leave_year=leave_year)

        leave_type_id = request.data.get("leave_type_id")

        if leave_type_id:
            queryset = queryset.filter(
                leave_type_id=leave_type_id,
            )

        serializer = EmployeeLeaveBalanceSerializer(
            queryset,
            many=True,
        )

        return self.success(
            "Your leave balances fetched successfully.",
            serializer.data,
        )


# =========================================================
# 6. ORGANIZATION LEAVE BALANCES
# =========================================================

class OrganizationLeaveBalanceListAPIView(LeaveBaseAPIView):

    def post(self, request):

        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        queryset = EmployeeLeaveBalance.objects.filter(
            organization=organization,
        ).select_related(
            "employee",
            "leave_type",
        )

        employee_id = request.data.get("employee_id")
        leave_type_id = request.data.get("leave_type_id")
        leave_year = request.data.get("leave_year")

        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        if leave_type_id:
            queryset = queryset.filter(leave_type_id=leave_type_id)

        if leave_year:
            try:
                leave_year = int(leave_year)
            except (TypeError, ValueError):
                return self.failure("Invalid leave_year.")

            queryset = queryset.filter(leave_year=leave_year)

        serializer = EmployeeLeaveBalanceSerializer(
            queryset,
            many=True,
        )

        return self.success(
            "Organization leave balances fetched successfully.",
            serializer.data,
        )


# =========================================================
# 7. INITIALIZE LEAVE BALANCES
# =========================================================

class LeaveBalanceInitializeAPIView(LeaveBaseAPIView):

    def post(self, request):

        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        try:
            leave_year = int(request.data.get("leave_year"))

            if leave_year < 1900 or leave_year > 9999:
                raise ValueError

        except (TypeError, ValueError):
            return self.failure(
                "A valid leave_year is required."
            )

        leave_type_ids = request.data.get("leave_type_ids")

        if leave_type_ids is not None:
            if not isinstance(leave_type_ids, list):
                return self.failure(
                    "leave_type_ids must be a list."
                )

            if leave_type_ids:
                valid_count = LeaveType.objects.filter(
                    organization=organization,
                    is_active=True,
                    id__in=leave_type_ids,
                ).count()

                if valid_count != len(set(leave_type_ids)):
                    return self.failure(
                        "One or more leave types are invalid or inactive."
                    )

        try:
            result = initialize_leave_balances(
                organization=organization,
                leave_year=leave_year,
                leave_type_ids=leave_type_ids,
                created_by=request.user,
            )
        except Exception:
            return self.failure(
                "Unable to initialize leave balances.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return self.success(
            "Leave balances initialized successfully.",
            result,
        )


# =========================================================
# 8. ADJUST LEAVE BALANCE
# =========================================================

class LeaveBalanceAdjustAPIView(LeaveBaseAPIView):

    def post(self, request):

        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        balance_id = request.data.get("balance_id")
        days = request.data.get("days")
        remarks = request.data.get("remarks", "")

        if not balance_id:
            return self.failure("balance_id is required.")

        if days is None:
            return self.failure("days is required.")

        try:
            days = Decimal(str(days))
        except (InvalidOperation, TypeError, ValueError):
            return self.failure("days must be a valid number.")

        if days == Decimal("0"):
            return self.failure("Adjustment days cannot be zero.")

        try:
            balance = adjust_leave_balance(
                balance_id=balance_id,
                organization=organization,
                days=days,
                created_by=request.user,
                remarks=remarks,
            )
        except ValueError as exc:
            return self.failure(str(exc))
        except Exception:
            return self.failure(
                "Unable to adjust leave balance.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return self.success(
            "Leave balance adjusted successfully.",
            EmployeeLeaveBalanceSerializer(balance).data,
        )


# =========================================================
# 9. CREATE LEAVE APPLICATION
# Employee only
# =========================================================

class LeaveApplicationCreateAPIView(LeaveBaseAPIView):

    def post(self, request):

        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        employee = self.get_employee(request, organization)

        if not employee:
            return self.failure(
                "No active employee profile is linked to this user.",
                status.HTTP_404_NOT_FOUND,
            )

        leave_type_id = request.data.get("leave_type_id")
        reason = request.data.get("reason", "")

        if not leave_type_id:
            return self.failure("leave_type_id is required.")

        leave_type = LeaveType.objects.filter(
            id=leave_type_id,
            organization=organization,
            is_active=True,
        ).first()

        if not leave_type:
            return self.failure(
                "Leave type not found or inactive.",
                status.HTTP_404_NOT_FOUND,
            )

        try:
            start_date = self.parse_date(
                request.data.get("start_date"),
                "start_date",
            )
            end_date = self.parse_date(
                request.data.get("end_date"),
                "end_date",
            )

            application = create_leave_application(
                employee=employee,
                organization=organization,
                leave_type=leave_type,
                start_date=start_date,
                end_date=end_date,
                reason=reason,
                created_by=request.user,
            )

        except ValueError as exc:
            return self.failure(str(exc))
        except Exception:
            return self.failure(
                "Unable to submit leave application.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return self.success(
            "Leave application submitted successfully.",
            LeaveApplicationSerializer(application).data,
            status.HTTP_201_CREATED,
        )


# =========================================================
# 10. MY LEAVE APPLICATIONS
# Employee only
# =========================================================

class MyLeaveApplicationListAPIView(LeaveBaseAPIView):

    def post(self, request):

        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        employee = self.get_employee(request, organization)

        if not employee:
            return self.failure(
                "No active employee profile is linked to this user.",
                status.HTTP_404_NOT_FOUND,
            )

        queryset = LeaveApplication.objects.filter(
            organization=organization,
            employee=employee,
        ).select_related(
            "leave_type",
            "reviewed_by",
        )

        application_status = request.data.get("status")

        if application_status:
            valid_statuses = dict(LeaveApplication.STATUS_CHOICES)

            if application_status not in valid_statuses:
                return self.failure("Invalid application status.")

            queryset = queryset.filter(status=application_status)

        serializer = LeaveApplicationSerializer(
            queryset,
            many=True,
        )

        return self.success(
            "Your leave applications fetched successfully.",
            serializer.data,
        )


# =========================================================
# 11. ORGANIZATION LEAVE APPLICATIONS
# =========================================================

class OrganizationLeaveApplicationListAPIView(LeaveBaseAPIView):

    def post(self, request):

        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        queryset = LeaveApplication.objects.filter(
            organization=organization,
        ).select_related(
            "employee",
            "leave_type",
            "reviewed_by",
        )

        application_status = request.data.get("status")

        if application_status:
            valid_statuses = dict(LeaveApplication.STATUS_CHOICES)

            if application_status not in valid_statuses:
                return self.failure("Invalid application status.")

            queryset = queryset.filter(status=application_status)

        employee_id = request.data.get("employee_id")
        leave_type_id = request.data.get("leave_type_id")

        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        if leave_type_id:
            queryset = queryset.filter(leave_type_id=leave_type_id)

        from_date = request.data.get("from_date")
        to_date = request.data.get("to_date")

        try:
            if from_date:
                from_date = self.parse_date(from_date, "from_date")

            if to_date:
                to_date = self.parse_date(to_date, "to_date")

        except ValueError as exc:
            return self.failure(str(exc))

        # Include applications that overlap the requested date range.
        if from_date and to_date:
            queryset = queryset.filter(
                start_date__lte=to_date,
                end_date__gte=from_date,
            )
        elif from_date:
            queryset = queryset.filter(end_date__gte=from_date)
        elif to_date:
            queryset = queryset.filter(start_date__lte=to_date)

        serializer = LeaveApplicationSerializer(
            queryset,
            many=True,
        )

        return self.success(
            "Leave applications fetched successfully.",
            serializer.data,
        )


# =========================================================
# 12. REVIEW LEAVE APPLICATION
# =========================================================

class LeaveApplicationReviewAPIView(LeaveBaseAPIView):

    def post(self, request):

        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        application_id = request.data.get("application_id")
        decision = request.data.get("decision")
        review_remarks = request.data.get("review_remarks", "")

        if not application_id:
            return self.failure("application_id is required.")

        if decision not in ["APPROVED", "REJECTED"]:
            return self.failure(
                "decision must be APPROVED or REJECTED."
            )

        try:
            application = review_leave_application(
                application_id=application_id,
                organization=organization,
                reviewed_by=request.user,
                approve=(decision == "APPROVED"),
                review_remarks=review_remarks,
            )
        except ValueError as exc:
            return self.failure(str(exc))
        except Exception:
            return self.failure(
                "Unable to review leave application.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return self.success(
            f"Leave application {application.status.lower()} successfully.",
            LeaveApplicationSerializer(application).data,
        )


# =========================================================
# 13. EMPLOYEE CANCEL OWN APPLICATION
# =========================================================

class MyLeaveApplicationCancelAPIView(LeaveBaseAPIView):

    def post(self, request):

        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        employee = self.get_employee(request, organization)

        if not employee:
            return self.failure(
                "No active employee profile is linked to this user.",
                status.HTTP_404_NOT_FOUND,
            )

        application_id = request.data.get("application_id")

        if not application_id:
            return self.failure("application_id is required.")

        try:
            application = cancel_leave_application(
                application_id=application_id,
                organization=organization,
                cancelled_by=request.user,
                employee=employee,
            )
        except ValueError as exc:
            return self.failure(str(exc))
        except Exception:
            return self.failure(
                "Unable to cancel leave application.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return self.success(
            "Leave application cancelled successfully.",
            LeaveApplicationSerializer(application).data,
        )


# =========================================================
# 14. ORGANIZATION CANCEL APPLICATION
# =========================================================

class OrganizationLeaveApplicationCancelAPIView(LeaveBaseAPIView):

    def post(self, request):

        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        application_id = request.data.get("application_id")

        if not application_id:
            return self.failure("application_id is required.")

        try:
            application = cancel_leave_application(
                application_id=application_id,
                organization=organization,
                cancelled_by=request.user,
            )
        except ValueError as exc:
            return self.failure(str(exc))
        except Exception:
            return self.failure(
                "Unable to cancel leave application.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return self.success(
            "Leave application cancelled successfully.",
            LeaveApplicationSerializer(application).data,
        )


# =========================================================
# 15. ORGANIZATION LEAVE TRANSACTIONS
# =========================================================

class OrganizationLeaveTransactionListAPIView(LeaveBaseAPIView):

    def post(self, request):

        organization, error_response = self.get_organization(request)

        if error_response:
            return error_response

        queryset = LeaveBalanceTransaction.objects.filter(
            organization=organization,
        ).select_related(
            "employee",
            "leave_type",
            "leave_balance",
            "leave_application",
            "created_by",
        )

        employee_id = request.data.get("employee_id")
        leave_type_id = request.data.get("leave_type_id")
        transaction_type = request.data.get("transaction_type")

        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        if leave_type_id:
            queryset = queryset.filter(leave_type_id=leave_type_id)

        if transaction_type:
            valid_types = dict(
                LeaveBalanceTransaction.TRANSACTION_TYPE_CHOICES
            )

            if transaction_type not in valid_types:
                return self.failure("Invalid transaction_type.")

            queryset = queryset.filter(
                transaction_type=transaction_type,
            )

        serializer = LeaveBalanceTransactionSerializer(
            queryset,
            many=True,
        )

        return self.success(
            "Leave balance transactions fetched successfully.",
            serializer.data,
        )
