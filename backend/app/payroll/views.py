"""
Payroll API views.

36 endpoints:
  Super admin (8)     — statutory rate configs + slabs, gated by is_superuser
  Org admin (25)      — full payroll lifecycle
  Employee (3)        — self-service

All POST. All return {status, message, data?, errors?}.
All org-scoped views use get_user_organization.
All writes call log_activity.
"""

from datetime import date as date_type
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.services import get_user_organization
from app.audit.services import log_activity
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
from .serializers import (
    PayrollSettingsSerializer,
    CompanyStatutorySettingsSerializer,
    SalaryComponentSerializer,
    SalaryStructureSerializer,
    SalaryStructureComponentInputSerializer,
    EmployeeSalaryAssignmentSerializer,
    StatutoryRateConfigSerializer,
    StatutorySlabSerializer,
    PayrollRunSerializer,
    PayrollRecordSerializer,
    PayrollPaymentSerializer,
)
from .services import (
    compute_cycle_period,
    compute_payslip_data,
    generate_payroll,
    finalize_payroll,
    recompute_payroll_record,
    update_payroll_record_deductions,
    bulk_assign_salary,
    bulk_close_salary_assignments,
    record_payment,
    bulk_record_payment_for_run,
)


# =========================================================
# BASE VIEWS
# =========================================================

class PayrollBaseAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def get_organization(self, request):
        org, err = get_user_organization(request)
        if err:
            return None, err
        return org, None

    def success(self, message, data=None, http_status=status.HTTP_200_OK):
        payload = {"status": True, "message": message}
        if data is not None:
            payload["data"] = data
        return Response(payload, status=http_status)

    def failure(self, message, http_status=status.HTTP_400_BAD_REQUEST, errors=None):
        payload = {"status": False, "message": message}
        if errors is not None:
            payload["errors"] = errors
        return Response(payload, status=http_status)

    def get_employee(self, request, organization):
        return Employee.objects.filter(
            user=request.user,
            organization=organization,
            is_active=True,
            employment_status="ACTIVE",
        ).first()

    def parse_date(self, value, field_name):
        if not value:
            return None
        try:
            return date_type.fromisoformat(str(value))
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must use YYYY-MM-DD format.")

    def parse_int(self, value, field_name):
        if value is None or value == "":
            raise ValueError(f"{field_name} is required.")
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be an integer.")

    def parse_decimal(self, value, field_name):
        if value is None or value == "":
            raise ValueError(f"{field_name} is required.")
        try:
            return Decimal(str(value))
        except (TypeError, ValueError, InvalidOperation):
            raise ValueError(f"{field_name} must be a valid number.")

    def parse_bool(self, value, field_name):
        """
        Accept real bools and 'true'/'false'/'1'/'0' strings.
        Reject anything else with a clear error.
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"true", "1"}:
                return True
            if v in {"false", "0", ""}:
                return False
        raise ValueError(f"{field_name} must be true or false.")

    def audit(self, **kwargs):
        try:
            log_activity(**kwargs)
        except Exception:
            pass


class SuperAdminBaseAPIView(PayrollBaseAPIView):
    """Base for super-admin-only endpoints."""

    def require_super_admin(self, request):
        if not request.user.is_superuser:
            return self.failure(
                "Only super administrators can access this resource.",
                status.HTTP_403_FORBIDDEN,
            )
        return None


# =========================================================
# =========================================================
# SUPER ADMIN — STATUTORY RATE CONFIGS (3 endpoints)
# =========================================================
# =========================================================

class StatutoryRateConfigListAPIView(SuperAdminBaseAPIView):

    def post(self, request):
        err = self.require_super_admin(request)
        if err:
            return err

        queryset = StatutoryRateConfig.objects.all().select_related("organization")

        component_code = request.data.get("component_code")
        organization_id = request.data.get("organization_id")
        include_federal = request.data.get("include_federal", True)

        if component_code:
            queryset = queryset.filter(component_code=component_code)

        if organization_id:
            queryset = queryset.filter(organization_id=organization_id)
        elif not include_federal:
            queryset = queryset.filter(organization__isnull=False)

        queryset = queryset.order_by("component_code", "-effective_from")

        serializer = StatutoryRateConfigSerializer(queryset, many=True)
        return self.success("Statutory rate configs fetched.", serializer.data)


class StatutoryRateConfigCreateAPIView(SuperAdminBaseAPIView):

    @transaction.atomic
    def post(self, request):
        err = self.require_super_admin(request)
        if err:
            return err

        data = request.data.copy()
        data.pop("id", None)

        serializer = StatutoryRateConfigSerializer(data=data)
        if not serializer.is_valid():
            return self.failure(
                "Invalid statutory rate config.", errors=serializer.errors,
            )

        config = serializer.save(
            created_by=request.user,
            updated_by=request.user,
        )

        self.audit(
            request=request,
            user=request.user,
            action="CREATE",
            module="PAYROLL",
            object_type="StatutoryRateConfig",
            object_id=config.id,
            description=(
                f"Statutory rate config created: {config.component_code} "
                f"= {config.rate_percentage}% from {config.effective_from}."
            ),
            new_data=StatutoryRateConfigSerializer(config).data,
        )

        return self.success(
            "Statutory rate config created.",
            StatutoryRateConfigSerializer(config).data,
            status.HTTP_201_CREATED,
        )


class StatutoryRateConfigUpdateAPIView(SuperAdminBaseAPIView):

    @transaction.atomic
    def post(self, request):
        err = self.require_super_admin(request)
        if err:
            return err

        try:
            config_id = self.parse_int(request.data.get("id"), "id")
        except ValueError as exc:
            return self.failure(str(exc))

        config = StatutoryRateConfig.objects.filter(id=config_id).first()
        if not config:
            return self.failure(
                "Statutory rate config not found.",
                status.HTTP_404_NOT_FOUND,
            )

        old_data = StatutoryRateConfigSerializer(config).data

        serializer = StatutoryRateConfigSerializer(
            config, data=request.data, partial=True,
        )
        if not serializer.is_valid():
            return self.failure(
                "Invalid statutory rate config.", errors=serializer.errors,
            )

        config = serializer.save(updated_by=request.user)

        self.audit(
            request=request,
            user=request.user,
            action="UPDATE",
            module="PAYROLL",
            object_type="StatutoryRateConfig",
            object_id=config.id,
            description=f"Statutory rate config updated: {config.component_code}.",
            old_data=old_data,
            new_data=StatutoryRateConfigSerializer(config).data,
        )

        return self.success(
            "Statutory rate config updated.",
            StatutoryRateConfigSerializer(config).data,
        )


# =========================================================
# =========================================================
# SUPER ADMIN — STATUTORY SLABS (3 endpoints)
# =========================================================
# =========================================================

class StatutorySlabListAPIView(SuperAdminBaseAPIView):

    def post(self, request):
        err = self.require_super_admin(request)
        if err:
            return err

        queryset = StatutorySlab.objects.all().select_related("state")

        slab_type = request.data.get("slab_type")
        state_id = request.data.get("state_id")

        if slab_type:
            queryset = queryset.filter(slab_type=slab_type)
        if state_id:
            queryset = queryset.filter(state_id=state_id)

        queryset = queryset.order_by("slab_type", "state", "income_from")

        serializer = StatutorySlabSerializer(queryset, many=True)
        return self.success("Statutory slabs fetched.", serializer.data)


class StatutorySlabCreateAPIView(SuperAdminBaseAPIView):

    @transaction.atomic
    def post(self, request):
        err = self.require_super_admin(request)
        if err:
            return err

        data = request.data.copy()
        data.pop("id", None)

        serializer = StatutorySlabSerializer(data=data)
        if not serializer.is_valid():
            return self.failure(
                "Invalid statutory slab.", errors=serializer.errors,
            )

        slab = serializer.save(
            created_by=request.user,
            updated_by=request.user,
        )

        self.audit(
            request=request,
            user=request.user,
            action="CREATE",
            module="PAYROLL",
            object_type="StatutorySlab",
            object_id=slab.id,
            description=(
                f"Statutory slab created: {slab.slab_type} "
                f"({slab.income_from} - {slab.income_to or '∞'})."
            ),
            new_data=StatutorySlabSerializer(slab).data,
        )

        return self.success(
            "Statutory slab created.",
            StatutorySlabSerializer(slab).data,
            status.HTTP_201_CREATED,
        )


class StatutorySlabUpdateAPIView(SuperAdminBaseAPIView):

    @transaction.atomic
    def post(self, request):
        err = self.require_super_admin(request)
        if err:
            return err

        try:
            slab_id = self.parse_int(request.data.get("id"), "id")
        except ValueError as exc:
            return self.failure(str(exc))

        slab = StatutorySlab.objects.filter(id=slab_id).first()
        if not slab:
            return self.failure(
                "Statutory slab not found.", status.HTTP_404_NOT_FOUND,
            )

        old_data = StatutorySlabSerializer(slab).data

        serializer = StatutorySlabSerializer(slab, data=request.data, partial=True)
        if not serializer.is_valid():
            return self.failure(
                "Invalid statutory slab.", errors=serializer.errors,
            )

        slab = serializer.save(updated_by=request.user)

        self.audit(
            request=request,
            user=request.user,
            action="UPDATE",
            module="PAYROLL",
            object_type="StatutorySlab",
            object_id=slab.id,
            description=f"Statutory slab updated: {slab.slab_type}.",
            old_data=old_data,
            new_data=StatutorySlabSerializer(slab).data,
        )

        return self.success(
            "Statutory slab updated.",
            StatutorySlabSerializer(slab).data,
        )


# =========================================================
# =========================================================
# ORG ADMIN — PAYROLL SETTINGS (1 endpoint, get or update)
# =========================================================
# =========================================================

class PayrollSettingsAPIView(PayrollBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        settings_obj, _ = PayrollSettings.objects.get_or_create(
            organization=organization,
        )

        body_keys = set(request.data.keys())
        if not body_keys or body_keys <= {"organization_id"}:
            return self.success(
                "Payroll settings fetched.",
                PayrollSettingsSerializer(settings_obj).data,
            )

        old_data = PayrollSettingsSerializer(settings_obj).data

        serializer = PayrollSettingsSerializer(
            settings_obj, data=request.data, partial=True,
        )
        if not serializer.is_valid():
            return self.failure(
                "Invalid payroll settings.", errors=serializer.errors,
            )

        settings_obj = serializer.save(updated_by=request.user)

        self.audit(
            request=request,
            user=request.user,
            action="UPDATE",
            module="PAYROLL",
            object_type="PayrollSettings",
            object_id=settings_obj.id,
            description="Payroll settings updated.",
            old_data=old_data,
            new_data=PayrollSettingsSerializer(settings_obj).data,
        )

        return self.success(
            "Payroll settings updated.",
            PayrollSettingsSerializer(settings_obj).data,
        )


# =========================================================
# =========================================================
# ORG ADMIN — COMPANY STATUTORY SETTINGS (1 endpoint, get or update)
# =========================================================
# =========================================================

class CompanyStatutorySettingsAPIView(PayrollBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        settings_obj, _ = CompanyStatutorySettings.objects.get_or_create(
            organization=organization,
        )

        body_keys = set(request.data.keys())
        if not body_keys or body_keys <= {"organization_id"}:
            return self.success(
                "Statutory settings fetched.",
                CompanyStatutorySettingsSerializer(settings_obj).data,
            )

        old_data = CompanyStatutorySettingsSerializer(settings_obj).data

        serializer = CompanyStatutorySettingsSerializer(
            settings_obj, data=request.data, partial=True,
        )
        if not serializer.is_valid():
            return self.failure(
                "Invalid statutory settings.", errors=serializer.errors,
            )

        settings_obj = serializer.save(updated_by=request.user)

        self.audit(
            request=request,
            user=request.user,
            action="UPDATE",
            module="PAYROLL",
            object_type="CompanyStatutorySettings",
            object_id=settings_obj.id,
            description="Company statutory settings updated.",
            old_data=old_data,
            new_data=CompanyStatutorySettingsSerializer(settings_obj).data,
        )

        return self.success(
            "Statutory settings updated.",
            CompanyStatutorySettingsSerializer(settings_obj).data,
        )


# =========================================================
# =========================================================
# ORG ADMIN — SALARY COMPONENTS (2 endpoints: list + create)
# =========================================================
# =========================================================

class SalaryComponentListAPIView(PayrollBaseAPIView):

    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        queryset = SalaryComponent.objects.filter(
            Q(organization__isnull=True) | Q(organization=organization)
        ).select_related("organization")

        component_type = request.data.get("component_type")
        if component_type:
            queryset = queryset.filter(component_type=component_type)

        is_active = request.data.get("is_active")
        if is_active is not None:
            try:
                is_active_bool = self.parse_bool(is_active, "is_active")
            except ValueError as exc:
                return self.failure(str(exc))
            queryset = queryset.filter(is_active=is_active_bool)

        queryset = queryset.order_by("display_order", "name")

        serializer = SalaryComponentSerializer(
            queryset, many=True,
            context={"organization": organization},
        )
        return self.success("Salary components fetched.", serializer.data)


class SalaryComponentCreateAPIView(PayrollBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        data = request.data.copy()
        data.pop("organization_id", None)
        data["organization"] = organization.id

        serializer = SalaryComponentSerializer(
            data=data,
            context={"organization": organization, "request": request},
        )
        if not serializer.is_valid():
            return self.failure(
                "Invalid salary component.", errors=serializer.errors,
            )

        component = serializer.save(
            organization=organization,
            created_by=request.user,
            updated_by=request.user,
        )

        self.audit(
            request=request,
            user=request.user,
            action="CREATE",
            module="PAYROLL",
            object_type="SalaryComponent",
            object_id=component.id,
            description=(
                f"Salary component created: {component.name} "
                f"({component.code})."
            ),
            new_data=SalaryComponentSerializer(
                component, context={"organization": organization},
            ).data,
        )

        return self.success(
            "Salary component created.",
            SalaryComponentSerializer(
                component, context={"organization": organization},
            ).data,
            status.HTTP_201_CREATED,
        )


# =========================================================
# =========================================================
# ORG ADMIN — SALARY STRUCTURES (5 endpoints)
# =========================================================
# =========================================================

class SalaryStructureListAPIView(PayrollBaseAPIView):

    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        queryset = SalaryStructure.objects.filter(
            organization=organization,
        ).prefetch_related("components__salary_component")

        is_active = request.data.get("is_active")
        if is_active is not None:
            try:
                is_active_bool = self.parse_bool(is_active, "is_active")
            except ValueError as exc:
                return self.failure(str(exc))
            queryset = queryset.filter(is_active=is_active_bool)

        queryset = queryset.order_by("name")

        serializer = SalaryStructureSerializer(queryset, many=True)
        return self.success("Salary structures fetched.", serializer.data)


class SalaryStructureCreateAPIView(PayrollBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        components_data = request.data.get("components", [])

        if not isinstance(components_data, list) or not components_data:
            return self.failure(
                "components must be a non-empty list.",
            )

        header_data = {
            k: v for k, v in request.data.items()
            if k in {"name", "code", "description", "is_active"}
        }

        struct_serializer = SalaryStructureSerializer(
            data=header_data,
            context={"organization": organization, "request": request},
        )
        if not struct_serializer.is_valid():
            return self.failure(
                "Invalid salary structure.",
                errors=struct_serializer.errors,
            )

        comp_serializer = SalaryStructureComponentInputSerializer(
            data=components_data,
            many=True,
            context={"organization": organization},
        )
        if not comp_serializer.is_valid():
            return self.failure(
                "Invalid structure components.",
                errors=comp_serializer.errors,
            )

        # Duplicate component check
        seen = set()
        for entry in comp_serializer.validated_data:
            cid = entry["salary_component"]
            if cid in seen:
                return self.failure(
                    f"Duplicate component ID {cid} in structure.",
                )
            seen.add(cid)

        structure = struct_serializer.save(
            organization=organization,
            created_by=request.user,
            updated_by=request.user,
        )

        for comp_data in comp_serializer.validated_data:
            SalaryStructureComponent.objects.create(
                salary_structure=structure,
                salary_component_id=comp_data["salary_component"],
                amount=comp_data.get("amount"),
                percentage=comp_data.get("percentage"),
            )

        self.audit(
            request=request,
            user=request.user,
            action="CREATE",
            module="PAYROLL",
            object_type="SalaryStructure",
            object_id=structure.id,
            description=(
                f"Salary structure created: {structure.name} "
                f"({structure.code})."
            ),
            new_data=SalaryStructureSerializer(structure).data,
        )

        return self.success(
            "Salary structure created.",
            SalaryStructureSerializer(structure).data,
            status.HTTP_201_CREATED,
        )


class SalaryStructureDetailAPIView(PayrollBaseAPIView):

    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        try:
            structure_id = self.parse_int(
                request.data.get("structure_id"), "structure_id",
            )
        except ValueError as exc:
            return self.failure(str(exc))

        structure = SalaryStructure.objects.filter(
            id=structure_id,
            organization=organization,
        ).prefetch_related("components__salary_component").first()

        if not structure:
            return self.failure(
                "Salary structure not found.",
                status.HTTP_404_NOT_FOUND,
            )

        return self.success(
            "Salary structure fetched.",
            SalaryStructureSerializer(structure).data,
        )


class SalaryStructureUpdateAPIView(PayrollBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        try:
            structure_id = self.parse_int(
                request.data.get("structure_id"), "structure_id",
            )
        except ValueError as exc:
            return self.failure(str(exc))

        structure = SalaryStructure.objects.filter(
            id=structure_id,
            organization=organization,
        ).first()

        if not structure:
            return self.failure(
                "Salary structure not found.",
                status.HTTP_404_NOT_FOUND,
            )

        # ---- STEP 1: validate header (NO SAVE) ----
        header_data = {
            k: v for k, v in request.data.items()
            if k in {"name", "code", "description", "is_active"}
        }

        serializer = SalaryStructureSerializer(
            structure, data=header_data, partial=True,
            context={"organization": organization, "request": request},
        )
        if not serializer.is_valid():
            return self.failure(
                "Invalid salary structure.",
                errors=serializer.errors,
            )

        # ---- STEP 2: validate components if provided (NO SAVE) ----
        components_data = request.data.get("components", None)
        comp_serializer = None

        if components_data is not None:
            if not isinstance(components_data, list):
                return self.failure("components must be a list.")

            comp_serializer = SalaryStructureComponentInputSerializer(
                data=components_data,
                many=True,
                context={"organization": organization},
            )
            if not comp_serializer.is_valid():
                return self.failure(
                    "Invalid structure components.",
                    errors=comp_serializer.errors,
                )

            seen = set()
            for entry in comp_serializer.validated_data:
                cid = entry["salary_component"]
                if cid in seen:
                    return self.failure(
                        f"Duplicate component ID {cid} in structure.",
                    )
                seen.add(cid)

        # ---- STEP 3: all validations passed — NOW save ----
        old_data = SalaryStructureSerializer(structure).data

        structure = serializer.save(updated_by=request.user)

        if comp_serializer is not None:
            structure.components.all().delete()
            for comp_data in comp_serializer.validated_data:
                SalaryStructureComponent.objects.create(
                    salary_structure=structure,
                    salary_component_id=comp_data["salary_component"],
                    amount=comp_data.get("amount"),
                    percentage=comp_data.get("percentage"),
                )

        self.audit(
            request=request,
            user=request.user,
            action="UPDATE",
            module="PAYROLL",
            object_type="SalaryStructure",
            object_id=structure.id,
            description=f"Salary structure updated: {structure.name}.",
            old_data=old_data,
            new_data=SalaryStructureSerializer(structure).data,
        )

        return self.success(
            "Salary structure updated.",
            SalaryStructureSerializer(structure).data,
        )


class SalaryStructureDeactivateAPIView(PayrollBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        try:
            structure_id = self.parse_int(
                request.data.get("structure_id"), "structure_id",
            )
        except ValueError as exc:
            return self.failure(str(exc))

        structure = SalaryStructure.objects.filter(
            id=structure_id,
            organization=organization,
        ).first()

        if not structure:
            return self.failure(
                "Salary structure not found.",
                status.HTTP_404_NOT_FOUND,
            )

        if not structure.is_active:
            return self.failure("Salary structure is already inactive.")

        structure.is_active = False
        structure.updated_by = request.user
        structure.save(update_fields=["is_active", "updated_by", "updated_at"])

        self.audit(
            request=request,
            user=request.user,
            action="UPDATE",
            module="PAYROLL",
            object_type="SalaryStructure",
            object_id=structure.id,
            description=f"Salary structure deactivated: {structure.name}.",
            new_data={"is_active": False},
        )

        return self.success("Salary structure deactivated.")


# =========================================================
# =========================================================
# ORG ADMIN — SALARY ASSIGNMENTS (5 endpoints)
# =========================================================
# =========================================================

class SalaryAssignmentListAPIView(PayrollBaseAPIView):

    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        queryset = EmployeeSalaryAssignment.objects.filter(
            organization=organization,
        ).select_related("employee", "salary_structure")

        employee_id = request.data.get("employee_id")
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        as_of_date_raw = request.data.get("as_of_date")
        if as_of_date_raw:
            try:
                as_of = self.parse_date(as_of_date_raw, "as_of_date")
            except ValueError as exc:
                return self.failure(str(exc))

            if as_of is None:
                return self.failure("as_of_date is required.")

            queryset = queryset.filter(
                effective_from__lte=as_of,
            ).filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=as_of)
            )

        queryset = queryset.order_by("-effective_from")

        serializer = EmployeeSalaryAssignmentSerializer(queryset, many=True)
        return self.success("Salary assignments fetched.", serializer.data)


class SalaryAssignmentCreateAPIView(PayrollBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        data = request.data.copy()
        data.pop("organization_id", None)

        serializer = EmployeeSalaryAssignmentSerializer(
            data=data,
            context={"organization": organization, "request": request},
        )
        if not serializer.is_valid():
            return self.failure(
                "Invalid salary assignment.",
                errors=serializer.errors,
            )

        assignment = serializer.save(
            organization=organization,
            assigned_by=request.user,
        )

        self.audit(
            request=request,
            user=request.user,
            action="CREATE",
            module="PAYROLL",
            object_type="EmployeeSalaryAssignment",
            object_id=assignment.id,
            description=(
                f"Salary assignment created for "
                f"{assignment.employee.employee_code} → "
                f"{assignment.salary_structure.name}."
            ),
            new_data=EmployeeSalaryAssignmentSerializer(assignment).data,
        )

        return self.success(
            "Salary assignment created.",
            EmployeeSalaryAssignmentSerializer(assignment).data,
            status.HTTP_201_CREATED,
        )


class SalaryAssignmentUpdateAPIView(PayrollBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        try:
            assignment_id = self.parse_int(
                request.data.get("assignment_id"), "assignment_id",
            )
        except ValueError as exc:
            return self.failure(str(exc))

        assignment = EmployeeSalaryAssignment.objects.filter(
            id=assignment_id,
            organization=organization,
        ).first()

        if not assignment:
            return self.failure(
                "Salary assignment not found.",
                status.HTTP_404_NOT_FOUND,
            )

        # ---- Guard: block structural edits on assignments already
        #      used in a FINALIZED payroll run ----
        overlap_end = assignment.effective_to or date_type.max
        used_in_finalized = PayrollRecord.objects.filter(
            organization=organization,
            employee=assignment.employee,
            payroll_run__status="FINALIZED",
            payroll_run__period_start__lte=overlap_end,
            payroll_run__period_end__gte=assignment.effective_from,
        ).exists()

        if used_in_finalized:
            structural_fields = {"salary_structure", "effective_from"}
            attempted = structural_fields & set(request.data.keys())
            if attempted:
                return self.failure(
                    "Cannot change salary_structure or effective_from on "
                    "an assignment already used in a finalized payroll "
                    "run. Close this assignment (set effective_to) and "
                    "create a new assignment for the revision.",
                )

        old_data = EmployeeSalaryAssignmentSerializer(assignment).data

        data = request.data.copy()
        data.pop("assignment_id", None)
        data.pop("organization_id", None)

        serializer = EmployeeSalaryAssignmentSerializer(
            assignment, data=data, partial=True,
            context={"organization": organization, "request": request},
        )
        if not serializer.is_valid():
            return self.failure(
                "Invalid salary assignment.",
                errors=serializer.errors,
            )

        assignment = serializer.save()

        self.audit(
            request=request,
            user=request.user,
            action="UPDATE",
            module="PAYROLL",
            object_type="EmployeeSalaryAssignment",
            object_id=assignment.id,
            description=(
                f"Salary assignment updated for "
                f"{assignment.employee.employee_code}."
            ),
            old_data=old_data,
            new_data=EmployeeSalaryAssignmentSerializer(assignment).data,
        )

        return self.success(
            "Salary assignment updated.",
            EmployeeSalaryAssignmentSerializer(assignment).data,
        )


class SalaryAssignmentBulkAssignAPIView(PayrollBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        employee_ids = request.data.get("employee_ids")
        if not isinstance(employee_ids, list) or not employee_ids:
            return self.failure("employee_ids must be a non-empty list.")

        try:
            structure_id = self.parse_int(
                request.data.get("salary_structure_id"),
                "salary_structure_id",
            )
            effective_from = self.parse_date(
                request.data.get("effective_from"), "effective_from",
            )
            if effective_from is None:
                return self.failure("effective_from is required.")

            effective_to_raw = request.data.get("effective_to")
            effective_to = (
                self.parse_date(effective_to_raw, "effective_to")
                if effective_to_raw else None
            )
        except ValueError as exc:
            return self.failure(str(exc))

        try:
            created = bulk_assign_salary(
                organization=organization,
                employee_ids=employee_ids,
                salary_structure_id=structure_id,
                effective_from=effective_from,
                effective_to=effective_to,
                reason=request.data.get("reason"),
                assigned_by=request.user,
            )
        except ValueError as exc:
            return self.failure(str(exc))
        except Exception:
            return self.failure(
                "Unable to bulk assign salary.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return self.success(
            f"Salary assigned to {len(created)} employee(s).",
            {
                "created_count": len(created),
                "assignments": EmployeeSalaryAssignmentSerializer(
                    created, many=True,
                ).data,
            },
            status.HTTP_201_CREATED,
        )


class SalaryAssignmentBulkCloseAPIView(PayrollBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        assignment_ids = request.data.get("assignment_ids")
        if not isinstance(assignment_ids, list) or not assignment_ids:
            return self.failure("assignment_ids must be a non-empty list.")

        try:
            effective_to = self.parse_date(
                request.data.get("effective_to"), "effective_to",
            )
            if effective_to is None:
                return self.failure("effective_to is required.")
        except ValueError as exc:
            return self.failure(str(exc))

        try:
            closed = bulk_close_salary_assignments(
                organization=organization,
                assignment_ids=assignment_ids,
                effective_to=effective_to,
                closed_by=request.user,
            )
        except ValueError as exc:
            return self.failure(str(exc))
        except Exception:
            return self.failure(
                "Unable to bulk close assignments.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return self.success(
            f"{len(closed)} salary assignment(s) closed.",
            {
                "closed_count": len(closed),
                "assignments": EmployeeSalaryAssignmentSerializer(
                    closed, many=True,
                ).data,
            },
        )


# =========================================================
# =========================================================
# ORG ADMIN — PAYROLL RUNS (6 endpoints)
# =========================================================
# =========================================================

class PayrollRunPreviewAPIView(PayrollBaseAPIView):

    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        period_start_raw = request.data.get("period_start")
        period_end_raw = request.data.get("period_end")
        reference_month = request.data.get("reference_month")
        use_current_cycle = request.data.get("use_current_cycle", False)

        has_start = bool(period_start_raw)
        has_end = bool(period_end_raw)

        # ---- Strict mode detection ----
        if has_start and has_end:
            # Explicit dates
            try:
                period_start = self.parse_date(period_start_raw, "period_start")
                period_end = self.parse_date(period_end_raw, "period_end")
            except ValueError as exc:
                return self.failure(str(exc))
            if period_start is None or period_end is None:
                return self.failure("Invalid dates.")
            if period_end < period_start:
                return self.failure(
                    "period_end cannot be before period_start.",
                )

        elif has_start or has_end:
            # Only one date supplied — reject
            return self.failure(
                "Provide both period_start and period_end, "
                "or neither (for auto-cycle).",
            )

        else:
            # Auto-cycle: reference_month OR use_current_cycle
            settings_obj = PayrollSettings.objects.filter(
                organization=organization,
            ).first()
            if not settings_obj:
                return self.failure(
                    "Payroll settings not configured. Set "
                    "cycle_start_day before using auto-period.",
                )

            reference = reference_month if reference_month else None
            if not use_current_cycle and not reference:
                return self.failure(
                    "Provide period_start + period_end, "
                    "or reference_month, or use_current_cycle=true.",
                )

            try:
                period_start, period_end = compute_cycle_period(
                    cycle_start_day=settings_obj.cycle_start_day,
                    reference=reference,
                )
            except ValueError as exc:
                return self.failure(str(exc))

        # ---- Rest of the preview logic unchanged ----
        employees = Employee.objects.filter(
            organization=organization,
            is_active=True,
            employment_status__in=["ACTIVE", "ON_LEAVE"],
        ).select_related("work_state").order_by("id")

        previews = []
        errors = []
        total_gross = Decimal("0.00")
        total_deductions = Decimal("0.00")
        total_net = Decimal("0.00")
        review_count = 0

        for employee in employees.iterator():
            try:
                data = compute_payslip_data(
                    employee=employee,
                    organization=organization,
                    period_start=period_start,
                    period_end=period_end,
                )
            except ValueError as exc:
                errors.append({
                    "employee_id": employee.id,
                    "employee_code": employee.employee_code,
                    "employee_name": (
                        f"{employee.first_name} {employee.last_name}".strip()
                    ),
                    "message": str(exc),
                })
                continue

            if data["requires_review"]:
                review_count += 1

            total_gross += data["gross_earnings"]
            total_deductions += data["total_deductions"]
            total_net += data["net"]

            previews.append({
                "employee_id": employee.id,
                "employee_code": employee.employee_code,
                "employee_name": (
                    f"{employee.first_name} {employee.last_name}".strip()
                ),
                "present_days": str(data["present_days"]),
                "half_days": str(data["half_days"]),
                "absent_days": str(data["absent_days"]),
                "paid_leave_days": str(data["paid_leave_days"]),
                "unpaid_leave_days": str(data["unpaid_leave_days"]),
                "holiday_days": str(data["holiday_days"]),
                "weekly_off_days": str(data["weekly_off_days"]),
                "overtime_hours": str(data["overtime_hours"]),
                "gross_earnings": str(data["gross_earnings"]),
                "total_deductions": str(data["total_deductions"]),
                "net": str(data["net"]),
                "requires_review": data["requires_review"],
                "line_items": data["line_items"],
            })

        return self.success(
            "Payroll preview generated.",
            {
                "period_start": str(period_start),
                "period_end": str(period_end),
                "total_employees": len(previews),
                "employees_requiring_review": review_count,
                "total_gross": str(total_gross),
                "total_deductions": str(total_deductions),
                "total_net": str(total_net),
                "errors": errors,
                "employees": previews,
            },
        )


class PayrollRunCreateAPIView(PayrollBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        data = request.data.copy()
        data.pop("organization_id", None)

        serializer = PayrollRunSerializer(
            data=data,
            context={"organization": organization, "request": request},
        )
        if not serializer.is_valid():
            return self.failure(
                "Invalid payroll run.", errors=serializer.errors,
            )

        run = PayrollRun.objects.create(
            organization=organization,
            period_start=serializer.validated_data["period_start"],
            period_end=serializer.validated_data["period_end"],
            status="DRAFT",
            created_by=request.user,
        )

        self.audit(
            request=request,
            user=request.user,
            action="CREATE",
            module="PAYROLL",
            object_type="PayrollRun",
            object_id=run.id,
            description=(
                f"Payroll run created (DRAFT) for "
                f"{run.period_start} to {run.period_end}."
            ),
            new_data={
                "period_start": str(run.period_start),
                "period_end": str(run.period_end),
                "status": run.status,
            },
        )

        return self.success(
            "Payroll run created.",
            PayrollRunSerializer(run).data,
            status.HTTP_201_CREATED,
        )


class PayrollRunListAPIView(PayrollBaseAPIView):

    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        queryset = PayrollRun.objects.filter(organization=organization)

        run_status = request.data.get("status")
        if run_status:
            queryset = queryset.filter(status=run_status)

        queryset = queryset.order_by("-period_start")

        serializer = PayrollRunSerializer(queryset, many=True)
        return self.success("Payroll runs fetched.", serializer.data)


class PayrollRunDetailAPIView(PayrollBaseAPIView):

    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        try:
            run_id = self.parse_int(
                request.data.get("payroll_run_id"), "payroll_run_id",
            )
        except ValueError as exc:
            return self.failure(str(exc))

        run = PayrollRun.objects.filter(
            id=run_id, organization=organization,
        ).prefetch_related(
            "records__line_items",
            "records__payments",
            "records__employee",
        ).first()

        if not run:
            return self.failure(
                "Payroll run not found.", status.HTTP_404_NOT_FOUND,
            )

        # Attach records to the run data
        run_data = PayrollRunSerializer(run).data
        records = run.records.select_related("employee").prefetch_related(
            "line_items", "payments",
        ).order_by("employee__employee_code")
        run_data["records"] = PayrollRecordSerializer(records, many=True).data

        return self.success("Payroll run fetched.", run_data)


class PayrollRunGenerateAPIView(PayrollBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        try:
            run_id = self.parse_int(
                request.data.get("payroll_run_id"), "payroll_run_id",
            )
        except ValueError as exc:
            return self.failure(str(exc))

        run = PayrollRun.objects.filter(
            id=run_id, organization=organization,
        ).first()

        if not run:
            return self.failure(
                "Payroll run not found.", status.HTTP_404_NOT_FOUND,
            )

        try:
            result = generate_payroll(
                payroll_run=run,
                generated_by=request.user,
            )
        except ValueError as exc:
            return self.failure(str(exc))
        except Exception:
            return self.failure(
                "Unable to generate payroll.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return self.success(
            (
                f"Payroll generated. "
                f"{result['generated_count']} generated, "
                f"{result['skipped_count']} skipped, "
                f"{result['error_count']} errors."
            ),
            {
                "payroll_run_id": run.id,
                "status": run.status,
                "generated_count": result["generated_count"],
                "skipped_count": result["skipped_count"],
                "error_count": result["error_count"],
                "errors": result["errors"],
                "totals": {
                    "total_employees": run.total_employees,
                    "total_gross": str(run.total_gross),
                    "total_deductions": str(run.total_deductions),
                    "total_net": str(run.total_net),
                },
            },
        )


class PayrollRunFinalizeAPIView(PayrollBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        try:
            run_id = self.parse_int(
                request.data.get("payroll_run_id"), "payroll_run_id",
            )
        except ValueError as exc:
            return self.failure(str(exc))

        run = PayrollRun.objects.filter(
            id=run_id, organization=organization,
        ).first()

        if not run:
            return self.failure(
                "Payroll run not found.", status.HTTP_404_NOT_FOUND,
            )

        try:
            run = finalize_payroll(run, finalized_by=request.user)
        except ValueError as exc:
            return self.failure(str(exc))
        except Exception:
            return self.failure(
                "Unable to finalize payroll.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return self.success(
            "Payroll finalized.",
            PayrollRunSerializer(run).data,
        )


# =========================================================
# =========================================================
# ORG ADMIN — PAYROLL RECORDS (2 endpoints)
# =========================================================
# =========================================================

class PayrollRecordListAPIView(PayrollBaseAPIView):

    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        queryset = PayrollRecord.objects.filter(
            organization=organization,
        ).select_related(
            "employee", "payroll_run",
        ).prefetch_related("line_items", "payments")

        payroll_run_id = request.data.get("payroll_run_id")
        if payroll_run_id:
            queryset = queryset.filter(payroll_run_id=payroll_run_id)

        employee_id = request.data.get("employee_id")
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        payment_status = request.data.get("payment_status")
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)

        generation_status = request.data.get("generation_status")
        if generation_status:
            queryset = queryset.filter(generation_status=generation_status)

        queryset = queryset.order_by(
            "-payroll_run__period_start", "employee__employee_code",
        )

        serializer = PayrollRecordSerializer(queryset, many=True)
        return self.success("Payroll records fetched.", serializer.data)


class PayrollRecordUpdateDeductionsAPIView(PayrollBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        try:
            record_id = self.parse_int(
                request.data.get("payroll_record_id"), "payroll_record_id",
            )
        except ValueError as exc:
            return self.failure(str(exc))

        record = PayrollRecord.objects.filter(
            id=record_id, organization=organization,
        ).first()

        if not record:
            return self.failure(
                "Payroll record not found.", status.HTTP_404_NOT_FOUND,
            )

        tds_raw = request.data.get("tds")
        other_deductions_raw = request.data.get("other_deductions")
        review_notes = request.data.get("review_notes")
        recompute_raw = request.data.get("recompute", False)

        tds = None
        if tds_raw is not None:
            try:
                tds = self.parse_decimal(tds_raw, "tds")
            except ValueError as exc:
                return self.failure(str(exc))

        other_deductions = None
        if other_deductions_raw is not None:
            try:
                other_deductions = self.parse_decimal(
                    other_deductions_raw, "other_deductions",
                )
            except ValueError as exc:
                return self.failure(str(exc))

        try:
            recompute = self.parse_bool(recompute_raw, "recompute")
        except ValueError as exc:
            return self.failure(str(exc))

        if (
            tds is None
            and other_deductions is None
            and not review_notes
            and not recompute
        ):
            return self.failure(
                "Provide at least one of tds, other_deductions, "
                "review_notes, or recompute=true."
            )

        try:
            if recompute:
                record = recompute_payroll_record(
                    record=record,
                    recomputed_by=request.user,
                )

            if (
                tds is not None
                or other_deductions is not None
                or review_notes is not None
            ):
                record = update_payroll_record_deductions(
                    record=record,
                    tds=tds,
                    other_deductions=other_deductions,
                    review_notes=review_notes,
                    updated_by=request.user,
                )
        except ValueError as exc:
            return self.failure(str(exc))
        except Exception:
            return self.failure(
                "Unable to update payroll record.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        record.refresh_from_db()

        return self.success(
            "Payroll record updated.",
            PayrollRecordSerializer(record).data,
        )


# =========================================================
# =========================================================
# ORG ADMIN — PAYMENTS (3 endpoints)
# =========================================================
# =========================================================

class PaymentRecordAPIView(PayrollBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        try:
            record_id = self.parse_int(
                request.data.get("payroll_record_id"), "payroll_record_id",
            )
            amount = self.parse_decimal(request.data.get("amount"), "amount")
            payment_date = self.parse_date(
                request.data.get("payment_date"), "payment_date",
            )
            if payment_date is None:
                return self.failure("payment_date is required.")
        except ValueError as exc:
            return self.failure(str(exc))

        record = PayrollRecord.objects.filter(
            id=record_id, organization=organization,
        ).first()

        if not record:
            return self.failure(
                "Payroll record not found.", status.HTTP_404_NOT_FOUND,
            )

        payment_mode = request.data.get("payment_mode", "BANK_TRANSFER")

        try:
            payment = record_payment(
                payroll_record=record,
                amount=amount,
                payment_date=payment_date,
                payment_mode=payment_mode,
                transaction_reference=request.data.get("transaction_reference"),
                notes=request.data.get("notes"),
                recorded_by=request.user,
            )
        except ValueError as exc:
            return self.failure(str(exc))
        except Exception:
            return self.failure(
                "Unable to record payment.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        record.refresh_from_db()

        return self.success(
            "Payment recorded.",
            {
                "payment": PayrollPaymentSerializer(payment).data,
                "record_status": {
                    "payroll_record_id": record.id,
                    "net": str(record.net),
                    "paid_amount": str(record.paid_amount),
                    "remaining": str(record.net - record.paid_amount),
                    "payment_status": record.payment_status,
                },
            },
            status.HTTP_201_CREATED,
        )


class PaymentBulkRecordForRunAPIView(PayrollBaseAPIView):

    @transaction.atomic
    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        try:
            run_id = self.parse_int(
                request.data.get("payroll_run_id"), "payroll_run_id",
            )
            payment_date = self.parse_date(
                request.data.get("payment_date"), "payment_date",
            )
            if payment_date is None:
                return self.failure("payment_date is required.")
        except ValueError as exc:
            return self.failure(str(exc))

        run = PayrollRun.objects.filter(
            id=run_id, organization=organization,
        ).first()

        if not run:
            return self.failure(
                "Payroll run not found.", status.HTTP_404_NOT_FOUND,
            )

        employee_ids = request.data.get("employee_ids")
        if employee_ids is not None:
            if not isinstance(employee_ids, list) or not employee_ids:
                return self.failure(
                    "employee_ids must be a non-empty list when provided."
                )

        try:
            result = bulk_record_payment_for_run(
                payroll_run=run,
                payment_date=payment_date,
                payment_mode=request.data.get("payment_mode", "BANK_TRANSFER"),
                transaction_reference=request.data.get("transaction_reference"),
                notes=request.data.get("notes"),
                recorded_by=request.user,
                employee_ids=employee_ids,
            )
        except ValueError as exc:
            return self.failure(str(exc))
        except Exception:
            return self.failure(
                "Unable to record bulk payment.",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return self.success(
            (
                f"{result['payments_recorded']} payment(s) recorded, "
                f"{len(result['errors'])} failed."
            ),
            {
                "payroll_run_id": run.id,
                "payments_recorded": result["payments_recorded"],
                "failed_count": len(result["errors"]),
                "errors": result["errors"],
                "payments": PayrollPaymentSerializer(
                    result["payments"], many=True,
                ).data,
            },
            status.HTTP_201_CREATED,
        )


class PaymentListAPIView(PayrollBaseAPIView):

    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        queryset = PayrollPayment.objects.filter(
            organization=organization,
        ).select_related(
            "payroll_record__employee", "recorded_by",
        )

        payroll_record_id = request.data.get("payroll_record_id")
        if payroll_record_id:
            queryset = queryset.filter(payroll_record_id=payroll_record_id)

        payroll_run_id = request.data.get("payroll_run_id")
        if payroll_run_id:
            queryset = queryset.filter(
                payroll_record__payroll_run_id=payroll_run_id,
            )

        employee_id = request.data.get("employee_id")
        if employee_id:
            queryset = queryset.filter(payroll_record__employee_id=employee_id)

        queryset = queryset.order_by("-payment_date", "-created_at")

        serializer = PayrollPaymentSerializer(queryset, many=True)
        return self.success("Payments fetched.", serializer.data)


# =========================================================
# =========================================================
# EMPLOYEE — SELF-SERVICE (3 endpoints)
# =========================================================
# =========================================================

class MyPayslipListAPIView(PayrollBaseAPIView):

    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        employee = self.get_employee(request, organization)
        if not employee:
            return self.failure(
                "No active employee profile is linked to this user.",
                status.HTTP_404_NOT_FOUND,
            )

        # Only FINALIZED runs are visible to employees
        queryset = PayrollRecord.objects.filter(
            organization=organization,
            employee=employee,
            payroll_run__status="FINALIZED",
            generation_status="GENERATED",
        ).select_related(
            "payroll_run", "employee",
        ).prefetch_related(
            "line_items", "payments",
        ).order_by("-payroll_run__period_start")

        serializer = PayrollRecordSerializer(queryset, many=True)
        return self.success("Your payslips fetched.", serializer.data)


class MyPayslipDetailAPIView(PayrollBaseAPIView):

    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        employee = self.get_employee(request, organization)
        if not employee:
            return self.failure(
                "No active employee profile is linked to this user.",
                status.HTTP_404_NOT_FOUND,
            )

        try:
            record_id = self.parse_int(
                request.data.get("payroll_record_id"), "payroll_record_id",
            )
        except ValueError as exc:
            return self.failure(str(exc))

        record = PayrollRecord.objects.filter(
            id=record_id,
            organization=organization,
            employee=employee,
            payroll_run__status="FINALIZED",
            generation_status="GENERATED",
        ).select_related(
            "payroll_run", "employee",
        ).prefetch_related(
            "line_items", "payments",
        ).first()

        if not record:
            return self.failure(
                "Payslip not found.", status.HTTP_404_NOT_FOUND,
            )

        return self.success(
            "Payslip fetched.",
            PayrollRecordSerializer(record).data,
        )


class MySalaryAssignmentAPIView(PayrollBaseAPIView):

    def post(self, request):
        organization, err = self.get_organization(request)
        if err:
            return err

        employee = self.get_employee(request, organization)
        if not employee:
            return self.failure(
                "No active employee profile is linked to this user.",
                status.HTTP_404_NOT_FOUND,
            )

        today = timezone.localdate()

        assignment = EmployeeSalaryAssignment.objects.filter(
            organization=organization,
            employee=employee,
            effective_from__lte=today,
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=today)
        ).select_related("salary_structure").order_by("-effective_from").first()

        if not assignment:
            return self.failure(
                "No active salary assignment found.",
                status.HTTP_404_NOT_FOUND,
            )

        return self.success(
            "Your salary assignment fetched.",
            EmployeeSalaryAssignmentSerializer(assignment).data,
        )
