from rest_framework import serializers

from .models import (
    LeaveType,
    EmployeeLeaveBalance,
    LeaveApplication,
    LeaveBalanceTransaction,
)


class LeaveTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = LeaveType
        fields = [
            "id",
            "name",
            "code",
            "description",
            "annual_allocation",
            "is_paid",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_active",
            "created_at",
            "updated_at",
        ]


class EmployeeLeaveBalanceSerializer(serializers.ModelSerializer):

    employee_code = serializers.CharField(
        source="employee.employee_code",
        read_only=True,
    )
    employee_name = serializers.SerializerMethodField()
    leave_type_name = serializers.CharField(
        source="leave_type.name",
        read_only=True,
    )
    available_days = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeLeaveBalance
        fields = [
            "id",
            "employee",
            "employee_code",
            "employee_name",
            "leave_type",
            "leave_type_name",
            "leave_year",
            "opening_balance",
            "allocated_days",
            "used_days",
            "pending_days",
            "available_days",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def get_employee_name(self, obj):
        return " ".join(
            filter(
                None,
                [
                    obj.employee.first_name,
                    obj.employee.middle_name,
                    obj.employee.last_name,
                ],
            )
        )

    def get_available_days(self, obj):
        return obj.available


class LeaveApplicationSerializer(serializers.ModelSerializer):

    employee_code = serializers.CharField(
        source="employee.employee_code",
        read_only=True,
    )
    employee_name = serializers.SerializerMethodField()
    leave_type_name = serializers.CharField(
        source="leave_type.name",
        read_only=True,
    )
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = LeaveApplication
        fields = [
            "id",
            "employee",
            "employee_code",
            "employee_name",
            "leave_type",
            "leave_type_name",
            "start_date",
            "end_date",
            "total_days",
            "reason",
            "status",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "review_remarks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "employee",
            "total_days",
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_remarks",
            "created_at",
            "updated_at",
        ]

    def get_employee_name(self, obj):
        return " ".join(
            filter(
                None,
                [
                    obj.employee.first_name,
                    obj.employee.middle_name,
                    obj.employee.last_name,
                ],
            )
        )

    def get_reviewed_by_name(self, obj):
        if not obj.reviewed_by:
            return None

        return (
            obj.reviewed_by.get_full_name()
            or obj.reviewed_by.username
        )


class LeaveBalanceTransactionSerializer(serializers.ModelSerializer):

    employee_code = serializers.CharField(
        source="employee.employee_code",
        read_only=True,
    )
    employee_name = serializers.SerializerMethodField()
    leave_type_name = serializers.CharField(
        source="leave_type.name",
        read_only=True,
    )

    class Meta:
        model = LeaveBalanceTransaction
        fields = [
            "id",
            "employee",
            "employee_code",
            "employee_name",
            "leave_type",
            "leave_type_name",
            "leave_balance",
            "leave_application",
            "transaction_type",
            "days",
            "remarks",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields

    def get_employee_name(self, obj):
        return " ".join(
            filter(
                None,
                [
                    obj.employee.first_name,
                    obj.employee.middle_name,
                    obj.employee.last_name,
                ],
            )
        )
