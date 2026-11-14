"""
Serializers for the payroll app.

All validation lives in `validate()` — no DB constraints, per project rule.
All POST, all `{status, message, data}` envelope handled in views.
"""

from datetime import date as date_type
from decimal import Decimal

from django.db.models import Q
from rest_framework import serializers

from app.employees.models import Employee

from .models import (
    PayrollSettings,
    CompanyStatutorySettings,
    SalaryComponent,
    SalaryStructure,
    SalaryStructureComponent,
    EmployeeSalaryAssignment,
    StatutoryRateConfig,
    StatutorySlab,
    PayrollRun,
    PayrollRecord,
    PayrollLineItem,
    PayrollPayment,
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


def _validate_effective_dates(effective_from, effective_to):
    if effective_from and effective_to and effective_to < effective_from:
        raise serializers.ValidationError({
            "effective_to": "End date cannot be before start date."
        })


# =========================================================
# PAYROLL SETTINGS
# =========================================================

class PayrollSettingsSerializer(serializers.ModelSerializer):

    class Meta:
        model = PayrollSettings
        fields = [
            "id",
            "organization",
            "cycle_start_day",
            "default_pay_day",
            "currency",
            "salary_basis",
            "absent_deduction_multiplier",
            "half_day_deduction_multiplier",
            "unpaid_leave_multiplier",
            "overtime_enabled",
            "overtime_rate_multiplier",
            "standard_work_hours_per_day",
            "missing_attendance_action",
            "payslip_mode",
            "payroll_enabled",
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

    def validate_cycle_start_day(self, value):
        if not (1 <= value <= 28):
            raise serializers.ValidationError(
                "cycle_start_day must be between 1 and 28."
            )
        return value

    def validate_default_pay_day(self, value):
        if not (1 <= value <= 31):
            raise serializers.ValidationError(
                "default_pay_day must be between 1 and 31."
            )
        return value

    def validate_standard_work_hours_per_day(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                "standard_work_hours_per_day must be greater than zero."
            )
        return value

    def validate_absent_deduction_multiplier(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Multiplier cannot be negative.")
        return value

    def validate_half_day_deduction_multiplier(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Multiplier cannot be negative.")
        return value

    def validate_unpaid_leave_multiplier(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Multiplier cannot be negative.")
        return value

    def validate_overtime_rate_multiplier(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Multiplier cannot be negative.")
        return value


# =========================================================
# COMPANY STATUTORY SETTINGS
# =========================================================

class CompanyStatutorySettingsSerializer(serializers.ModelSerializer):

    pt_state_name = serializers.CharField(
        source="pt_state.state_name",
        read_only=True,
        allow_null=True,
    )
    lwf_state_name = serializers.CharField(
        source="lwf_state.state_name",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = CompanyStatutorySettings
        fields = [
            "id",
            "organization",
            "is_pf_applicable",
            "pf_establishment_code",
            "pf_org_name",
            "pf_contribution_type",
            "is_esi_applicable",
            "esi_employer_code",
            "esi_org_name",
            "is_pt_applicable",
            "pt_state",
            "pt_state_name",
            "pt_registration_number",
            "is_tds_applicable",
            "tan_number",
            "tds_deductor_name",
            "tds_deductor_address",
            "is_lwf_applicable",
            "lwf_state",
            "lwf_state_name",
            "lwf_registration_number",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "pt_state_name",
            "lwf_state_name",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        is_pt = attrs.get(
            "is_pt_applicable",
            getattr(self.instance, "is_pt_applicable", False),
        )
        pt_state = attrs.get(
            "pt_state",
            getattr(self.instance, "pt_state", None),
        )
        if is_pt and pt_state is None:
            raise serializers.ValidationError({
                "pt_state": "pt_state is required when PT is enabled."
            })

        is_lwf = attrs.get(
            "is_lwf_applicable",
            getattr(self.instance, "is_lwf_applicable", False),
        )
        lwf_state = attrs.get(
            "lwf_state",
            getattr(self.instance, "lwf_state", None),
        )
        if is_lwf and lwf_state is None:
            raise serializers.ValidationError({
                "lwf_state": "lwf_state is required when LWF is enabled."
            })

        return attrs


# =========================================================
# SALARY COMPONENT
# =========================================================

class SalaryComponentSerializer(serializers.ModelSerializer):

    class Meta:
        model = SalaryComponent
        fields = [
            "id",
            "organization",
            "name",
            "code",
            "description",
            "component_type",
            "calculation_type",
            "component_role",
            "percentage_of_component",
            "is_taxable",
            "is_pf_eligible",
            "is_esi_eligible",
            "is_active",
            "display_order",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        org = self.context.get("organization")
        if org is None and self.instance:
            org = self.instance.organization

        code = attrs.get("code", getattr(self.instance, "code", None))
        if not code:
            raise serializers.ValidationError({"code": "Code is required."})
        code = code.strip().upper()

        # Determine scope org
        if self.instance:
            scope_org = attrs.get(
                "organization",
                getattr(self.instance, "organization", None),
            )
        else:
            scope_org = org

        existing = SalaryComponent.objects.filter(code__iexact=code)
        if scope_org is None:
            existing = existing.filter(organization__isnull=True)
        else:
            existing = existing.filter(organization=scope_org)

        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise serializers.ValidationError({
                "code": (
                    f"A component with code '{code}' already exists "
                    f"in this scope."
                )
            })

        calc_type = attrs.get(
            "calculation_type",
            getattr(self.instance, "calculation_type", "FIXED"),
        )
        pct_parent = attrs.get(
            "percentage_of_component",
            getattr(self.instance, "percentage_of_component", None),
        )
        if calc_type == "PERCENTAGE" and pct_parent is None:
            raise serializers.ValidationError({
                "percentage_of_component": (
                    "percentage_of_component is required for PERCENTAGE "
                    "components."
                )
            })
        if calc_type == "FIXED" and pct_parent is not None:
            raise serializers.ValidationError({
                "percentage_of_component": (
                    "percentage_of_component must be empty for FIXED "
                    "components."
                )
            })

        if self.instance and pct_parent and pct_parent.pk == self.instance.pk:
            raise serializers.ValidationError({
                "percentage_of_component": (
                    "A component cannot reference itself."
                )
            })

        return attrs

    def create(self, validated_data):
        if "code" in validated_data:
            validated_data["code"] = validated_data["code"].strip().upper()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "code" in validated_data:
            validated_data["code"] = validated_data["code"].strip().upper()
        return super().update(instance, validated_data)


# =========================================================
# SALARY STRUCTURE COMPONENT (nested read helper)
# =========================================================

class SalaryStructureComponentSerializer(serializers.ModelSerializer):

    component_code = serializers.CharField(
        source="salary_component.code", read_only=True,
    )
    component_name = serializers.CharField(
        source="salary_component.name", read_only=True,
    )
    component_type = serializers.CharField(
        source="salary_component.component_type", read_only=True,
    )
    component_role = serializers.CharField(
        source="salary_component.component_role", read_only=True,
    )

    class Meta:
        model = SalaryStructureComponent
        fields = [
            "id",
            "salary_structure",
            "salary_component",
            "component_code",
            "component_name",
            "component_type",
            "component_role",
            "amount",
            "percentage",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "salary_structure",
            "component_code",
            "component_name",
            "component_type",
            "component_role",
            "created_at",
            "updated_at",
        ]


# =========================================================
# SALARY STRUCTURE
# =========================================================

class SalaryStructureSerializer(serializers.ModelSerializer):

    components = SalaryStructureComponentSerializer(many=True, read_only=True)
    total_gross = serializers.SerializerMethodField()

    class Meta:
        model = SalaryStructure
        fields = [
            "id",
            "organization",
            "name",
            "code",
            "description",
            "is_active",
            "components",
            "total_gross",
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
            "components",
            "total_gross",
        ]

    def get_total_gross(self, obj):
        # Sum of FIXED earnings only; percentage components depend on a base
        # wage and are excluded from the display total.
        total = Decimal("0.00")
        for entry in obj.components.all():
            comp = entry.salary_component
            if comp.component_type != "EARNING":
                continue
            if comp.calculation_type == "FIXED" and entry.amount:
                total += entry.amount
        return str(total)

    def validate(self, attrs):
        org = self.context.get("organization")
        if org is None and self.instance:
            org = self.instance.organization

        code = attrs.get("code", getattr(self.instance, "code", None))
        if not code:
            raise serializers.ValidationError({"code": "Code is required."})
        code = code.strip().upper()

        name = attrs.get("name", getattr(self.instance, "name", None))
        if not name:
            raise serializers.ValidationError({"name": "Name is required."})

        if org is not None:
            dup_code = SalaryStructure.objects.filter(
                organization=org,
                code__iexact=code,
            )
            if self.instance:
                dup_code = dup_code.exclude(pk=self.instance.pk)
            if dup_code.exists():
                raise serializers.ValidationError({
                    "code": (
                        f"A structure with code '{code}' already exists."
                    )
                })

            dup_name = SalaryStructure.objects.filter(
                organization=org,
                name__iexact=name.strip(),
            )
            if self.instance:
                dup_name = dup_name.exclude(pk=self.instance.pk)
            if dup_name.exists():
                raise serializers.ValidationError({
                    "name": (
                        f"A structure with name '{name}' already exists."
                    )
                })

        return attrs

    def create(self, validated_data):
        if "code" in validated_data:
            validated_data["code"] = validated_data["code"].strip().upper()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "code" in validated_data:
            validated_data["code"] = validated_data["code"].strip().upper()
        return super().update(instance, validated_data)


class SalaryStructureComponentInputSerializer(serializers.Serializer):
    """
    Input for the component list in `SalaryStructureCreateAPIView` and
    `SalaryStructureSetComponentsAPIView`. Fully replaces the structure's
    components atomically.
    """

    salary_component = serializers.IntegerField()
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    percentage = serializers.DecimalField(
        max_digits=6,
        decimal_places=4,
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        org = self.context.get("organization")
        if org is None:
            raise serializers.ValidationError(
                "Organization context is required."
            )

        comp_id = attrs.get("salary_component")
        component = SalaryComponent.objects.filter(id=comp_id).first()
        if component is None:
            raise serializers.ValidationError({
                "salary_component": f"Component {comp_id} not found."
            })

        if component.organization_id not in (None, org.id):
            raise serializers.ValidationError({
                "salary_component": (
                    f"Component {comp_id} does not belong to this "
                    "organization or to the global catalog."
                )
            })

        if not component.is_active:
            raise serializers.ValidationError({
                "salary_component": f"Component {comp_id} is inactive."
            })

        if component.calculation_type == "FIXED":
            if attrs.get("amount") is None:
                raise serializers.ValidationError({
                    "amount": "Amount is required for FIXED components."
                })
            if attrs.get("percentage") is not None:
                raise serializers.ValidationError({
                    "percentage": (
                        "Percentage must be empty for FIXED components."
                    )
                })
        elif component.calculation_type == "PERCENTAGE":
            if attrs.get("percentage") is None:
                raise serializers.ValidationError({
                    "percentage": (
                        "Percentage is required for PERCENTAGE components."
                    )
                })
            if attrs.get("amount") is not None:
                raise serializers.ValidationError({
                    "amount": (
                        "Amount must be empty for PERCENTAGE components."
                    )
                })

        return attrs


# =========================================================
# EMPLOYEE SALARY ASSIGNMENT
# =========================================================

class EmployeeSalaryAssignmentSerializer(serializers.ModelSerializer):

    employee_name = serializers.SerializerMethodField()
    employee_code = serializers.CharField(
        source="employee.employee_code", read_only=True,
    )
    salary_structure_name = serializers.CharField(
        source="salary_structure.name", read_only=True,
    )

    class Meta:
        model = EmployeeSalaryAssignment
        fields = [
            "id",
            "organization",
            "employee",
            "employee_code",
            "employee_name",
            "salary_structure",
            "salary_structure_name",
            "effective_from",
            "effective_to",
            "reason",
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
        org = self.context.get("organization")
        if org is None and self.instance:
            org = self.instance.organization
        if org is None:
            raise serializers.ValidationError(
                "Organization context is required."
            )

        employee = attrs.get(
            "employee",
            getattr(self.instance, "employee", None),
        )
        structure = attrs.get(
            "salary_structure",
            getattr(self.instance, "salary_structure", None),
        )
        effective_from = attrs.get(
            "effective_from",
            getattr(self.instance, "effective_from", None),
        )
        effective_to = attrs.get(
            "effective_to",
            getattr(self.instance, "effective_to", None),
        )

        if employee:
            if employee.organization_id != org.id:
                raise serializers.ValidationError({
                    "employee": (
                        "Employee does not belong to this organization."
                    )
                })
            if (
                not employee.is_active
                or employee.employment_status not in ("ACTIVE", "ON_LEAVE")
            ):
                raise serializers.ValidationError({
                    "employee": (
                        "Only active/on-leave employees can be assigned "
                        "a salary structure."
                    )
                })

        if structure:
            if structure.organization_id != org.id:
                raise serializers.ValidationError({
                    "salary_structure": (
                        "Structure does not belong to this organization."
                    )
                })
            if not structure.is_active:
                raise serializers.ValidationError({
                    "salary_structure": (
                        "Cannot assign an inactive salary structure."
                    )
                })

        _validate_effective_dates(effective_from, effective_to)

        if employee and effective_from:
            overlapping = EmployeeSalaryAssignment.objects.filter(
                organization=org,
                employee=employee,
                effective_from__lte=(
                    effective_to if effective_to is not None else date_type.max
                ),
            ).filter(
                Q(effective_to__isnull=True)
                | Q(effective_to__gte=effective_from)
            )
            if self.instance:
                overlapping = overlapping.exclude(pk=self.instance.pk)

            conflict = overlapping.select_related("salary_structure").first()
            if conflict:
                raise serializers.ValidationError({
                    "employee": (
                        f"Employee already has a salary assignment "
                        f"'{conflict.salary_structure.name}' from "
                        f"{conflict.effective_from} to "
                        f"{conflict.effective_to or 'open-ended'}. "
                        f"Assignment date ranges cannot overlap."
                    )
                })

        # Enforce cycle-boundary alignment: assignments must start on the
        # organization's configured cycle start day. This prevents mid-cycle
        # salary revisions, which the calculation layer does not support.
        if employee and effective_from and org is not None:
            from .models import PayrollSettings
            from .services import compute_cycle_period

            settings_obj = PayrollSettings.objects.filter(
                organization=org,
            ).first()

            if settings_obj:
                try:
                    cycle_start, _ = compute_cycle_period(
                        cycle_start_day=settings_obj.cycle_start_day,
                        reference=effective_from,
                    )
                except ValueError:
                    cycle_start = None

                if cycle_start and effective_from != cycle_start:
                    raise serializers.ValidationError({
                        "effective_from": (
                            f"Salary assignment must start on a cycle "
                            f"boundary. The cycle containing "
                            f"{effective_from} starts on {cycle_start}. "
                            f"Use {cycle_start} or a later cycle start as "
                            f"effective_from."
                        )
                    })

        return attrs


# =========================================================
# STATUTORY RATE CONFIG
# =========================================================

class StatutoryRateConfigSerializer(serializers.ModelSerializer):

    class Meta:
        model = StatutoryRateConfig
        fields = [
            "id",
            "organization",
            "component_code",
            "rate_percentage",
            "wage_ceiling",
            "calculation_base",
            "effective_from",
            "effective_to",
            "notification_reference",
            "notes",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        org = attrs.get(
            "organization",
            getattr(self.instance, "organization", None),
        )
        component_code = attrs.get(
            "component_code",
            getattr(self.instance, "component_code", None),
        )
        effective_from = attrs.get(
            "effective_from",
            getattr(self.instance, "effective_from", None),
        )
        effective_to = attrs.get(
            "effective_to",
            getattr(self.instance, "effective_to", None),
        )

        _validate_effective_dates(effective_from, effective_to)

        if component_code and effective_from:
            qs = StatutoryRateConfig.objects.filter(
                component_code=component_code,
                effective_from__lte=(
                    effective_to if effective_to is not None else date_type.max
                ),
            ).filter(
                Q(effective_to__isnull=True)
                | Q(effective_to__gte=effective_from)
            )
            if org is None:
                qs = qs.filter(organization__isnull=True)
            else:
                qs = qs.filter(organization=org)

            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                scope = (
                    "federal defaults" if org is None
                    else "this organization"
                )
                raise serializers.ValidationError({
                    "effective_from": (
                        f"An overlapping rate config already exists for "
                        f"{component_code} in {scope}."
                    )
                })

        return attrs


# =========================================================
# STATUTORY SLAB
# =========================================================

class StatutorySlabSerializer(serializers.ModelSerializer):

    state_name = serializers.CharField(
        source="state.state_name",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = StatutorySlab
        fields = [
            "id",
            "slab_type",
            "state",
            "state_name",
            "income_from",
            "income_to",
            "fixed_amount",
            "rate_percentage",
            "is_february_override",
            "additional_amount",
            "frequency",
            "effective_from",
            "effective_to",
            "notes",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "state_name",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        income_from = attrs.get(
            "income_from",
            getattr(self.instance, "income_from", None),
        )
        income_to = attrs.get(
            "income_to",
            getattr(self.instance, "income_to", None),
        )
        if (
            income_from is not None
            and income_to is not None
            and income_to < income_from
        ):
            raise serializers.ValidationError({
                "income_to": "income_to cannot be less than income_from."
            })

        effective_from = attrs.get(
            "effective_from",
            getattr(self.instance, "effective_from", None),
        )
        effective_to = attrs.get(
            "effective_to",
            getattr(self.instance, "effective_to", None),
        )
        _validate_effective_dates(effective_from, effective_to)

        slab_type = attrs.get(
            "slab_type",
            getattr(self.instance, "slab_type", None),
        )
        state = attrs.get(
            "state",
            getattr(self.instance, "state", None),
        )

        if slab_type == "PT" and state is None:
            raise serializers.ValidationError({
                "state": "State is required for PT slabs."
            })

        has_amount = attrs.get(
            "fixed_amount",
            getattr(self.instance, "fixed_amount", None),
        )
        has_rate = attrs.get(
            "rate_percentage",
            getattr(self.instance, "rate_percentage", None),
        )
        if has_amount is None and has_rate is None:
            raise serializers.ValidationError({
                "fixed_amount": (
                    "Either fixed_amount or rate_percentage is required."
                )
            })

        return attrs


# =========================================================
# PAYROLL RUN
# =========================================================

class PayrollRunSerializer(serializers.ModelSerializer):

    class Meta:
        model = PayrollRun
        fields = [
            "id",
            "organization",
            "period_start",
            "period_end",
            "status",
            "total_employees",
            "total_gross",
            "total_deductions",
            "total_net",
            "created_by",
            "finalized_by",
            "finalized_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "status",
            "total_employees",
            "total_gross",
            "total_deductions",
            "total_net",
            "created_by",
            "finalized_by",
            "finalized_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        period_start = attrs.get(
            "period_start",
            getattr(self.instance, "period_start", None),
        )
        period_end = attrs.get(
            "period_end",
            getattr(self.instance, "period_end", None),
        )

        if period_start and period_end and period_end < period_start:
            raise serializers.ValidationError({
                "period_end": (
                    "period_end cannot be before period_start."
                )
            })

        # Exact-period uniqueness: one run per (organization, period_start,
        # period_end). Overlapping periods are allowed here so that
        # correction runs can be created. The generate_payroll service
        # guards against double-payment via overlapping periods by
        # rejecting generation if any employee was already paid in an
        # overlapping run.
        org = self.context.get("organization")
        if org and period_start and period_end:
            existing = PayrollRun.objects.filter(
                organization=org,
                period_start=period_start,
                period_end=period_end,
            )
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError({
                    "period_start": (
                        "A payroll run already exists for this exact "
                        "period in this organization."
                    )
                })

        return attrs


# =========================================================
# PAYROLL LINE ITEM
# =========================================================

class PayrollLineItemSerializer(serializers.ModelSerializer):

    class Meta:
        model = PayrollLineItem
        fields = [
            "id",
            "payroll_record",
            "component_code",
            "component_name",
            "component_type",
            "amount",
            "calculation_details",
            "created_at",
        ]
        read_only_fields = fields


# =========================================================
# PAYROLL RECORD
# =========================================================

class PayrollRecordSerializer(serializers.ModelSerializer):

    employee_name = serializers.SerializerMethodField()
    employee_code = serializers.CharField(
        source="employee.employee_code", read_only=True,
    )
    period_start = serializers.DateField(
        source="payroll_run.period_start", read_only=True,
    )
    period_end = serializers.DateField(
        source="payroll_run.period_end", read_only=True,
    )
    payroll_month = serializers.SerializerMethodField()
    remaining = serializers.SerializerMethodField()
    upi_link = serializers.SerializerMethodField()
    line_items = PayrollLineItemSerializer(many=True, read_only=True)

    class Meta:
        model = PayrollRecord
        fields = [
            "id",
            "payroll_run",
            "organization",
            "employee",
            "employee_code",
            "employee_name",
            "period_start",
            "period_end",
            "payroll_month",
            "present_days",
            "half_days",
            "absent_days",
            "paid_leave_days",
            "unpaid_leave_days",
            "holiday_days",
            "weekly_off_days",
            "overtime_hours",
            "monthly_salary",
            "per_day_rate",
            "pf_employee",
            "pf_employer",
            "eps",
            "edli",
            "esi_employee",
            "esi_employer",
            "pt",
            "tds",
            "lwf_employee",
            "lwf_employer",
            "other_deductions",
            "gross_earnings",
            "total_deductions",
            "net",
            "payment_status",
            "paid_amount",
            "remaining",
            "upi_link",
            "generation_status",
            "generation_notes",
            "requires_review",
            "review_notes",
            "breakdown",
            "line_items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_employee_name(self, obj):
        return get_employee_full_name(obj.employee)

    def get_payroll_month(self, obj):
        return obj.payroll_run.period_start.strftime("%B %Y")

    def get_remaining(self, obj):
        return str(obj.net - obj.paid_amount)

    def get_upi_link(self, obj):
        from urllib.parse import quote

        upi_id = getattr(obj.employee, "upi_id", None)
        if not upi_id:
            return None

        remaining = obj.net - obj.paid_amount
        if remaining <= 0:
            return None

        name = get_employee_full_name(obj.employee) or obj.employee.employee_code
        note = f"{obj.payroll_run.period_start.strftime('%B %Y')} salary"

        return (
            f"upi://pay?"
            f"pa={quote(upi_id)}&"
            f"pn={quote(name)}&"
            f"am={remaining}&"
            f"cu=INR&"
            f"tn={quote(note)}"
        )


# =========================================================
# PAYROLL PAYMENT
# =========================================================

class PayrollPaymentSerializer(serializers.ModelSerializer):

    employee_code = serializers.CharField(
        source="payroll_record.employee.employee_code",
        read_only=True,
    )
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = PayrollPayment
        fields = [
            "id",
            "organization",
            "payroll_record",
            "employee_code",
            "employee_name",
            "amount",
            "payment_date",
            "payment_mode",
            "transaction_reference",
            "notes",
            "recorded_by",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "recorded_by",
            "created_at",
        ]

    def get_employee_name(self, obj):
        return get_employee_full_name(obj.payroll_record.employee)
