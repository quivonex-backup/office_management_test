from django.db import transaction
from django.db.models import Count, Q
from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError

from .models import Department, Designation, Employee, EmployeeDocument
from app.accounts.models import Role, OrganizationMembership
from app.accounts.services import is_super_admin

from .serializers import (
    EmployeeCreateSerializer,
    EmployeeListSerializer,
    EmployeeDetailSerializer,
    EmployeeUpdateSerializer,
    MyEmployeeProfileSerializer,
    DepartmentSerializer,
    DepartmentWriteSerializer,
    DesignationSerializer,
    DesignationWriteSerializer,
)

from common.services import get_user_organization, get_current_employee
from common.s3_utils import upload_to_s3, delete_from_s3
from app.audit.services import log_activity
from .services import create_employee_user, resolve_org_assignments, apply_org_assignments, close_open_assignments
from common.permissions import OrgAPIView, require_perm, has_perm, resolve_scope




# =========================================================
# CREATE EMPLOYEE
# =========================================================
class EmployeeCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        # -------------------------------------------------
        # GET ORGANIZATION
        # -------------------------------------------------
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        denied = require_perm(request, organization, "employee.update")
        if denied:
            return denied

        # -------------------------------------------------
        # VALIDATE EMPLOYEE DATA
        # -------------------------------------------------
        serializer = EmployeeCreateSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        create_user = serializer.validated_data.get("create_user", False)

        if create_user and not has_perm(request, organization, "employee.create_user"):
            return Response(
                {
                    "status": False,
                    "message": "You do not have permission to create user accounts.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Batch 1: branch / department / designation / access role / manager
        org_changes, org_errors = resolve_org_assignments(
            request.data,
            organization,
            employee=None,
            can_assign_access=has_perm(request, organization, "access.manage"),
        )

        if org_errors:
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": org_errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # CREATE EMPLOYEE
        # -------------------------------------------------
        employee = serializer.save(
            organization=organization,
            created_by=request.user,
            updated_by=request.user,
        )

        # -------------------------------------------------
        # GENERATE EMPLOYEE CODE
        # -------------------------------------------------
        employee.employee_code = f"EMP-{employee.id:06d}"
        employee.save(update_fields=["employee_code"])

        apply_org_assignments(
            employee,
            org_changes,
            text_sent={f for f in ("department", "designation") if f in request.data},
        )

        # -------------------------------------------------
        # CREATE USER ACCOUNT IF REQUESTED
        # -------------------------------------------------
        user = None
        membership = None

        if create_user:
            try:
                user, _generated_password = create_employee_user(employee)

                # Assign the Employee role to the new user.
                employee_role = Role.objects.filter(
                    name__iexact="Employee",
                    is_active=True,
                ).first()

                if not employee_role:
                    raise ValidationError(
                        {
                            "role": (
                                "An active Employee role must exist "
                                "before creating employee user accounts."
                            )
                        }
                    )

                user.role = employee_role
                user.save(update_fields=["role"])

                # Create organization membership for the new user.
                membership, _created = (
                    OrganizationMembership.objects.update_or_create(
                        organization=organization,
                        user=user,
                        defaults={"is_active": True},
                    )
                )

            except ValidationError as exc:
                transaction.set_rollback(True)

                return Response(
                    {
                        "status": False,
                        "message": "Unable to create employee user account.",
                        "errors": exc.detail,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # -------------------------------------------------
        # UPLOAD PROFILE PHOTO
        # -------------------------------------------------
        profile_photo = request.FILES.get("profile_photo")
        profile_photo_path = None

        if profile_photo:
            profile_photo_path = upload_to_s3(
                file=profile_photo,
                folder="employees/profile",
            )

            employee.profile_photo = profile_photo_path
            employee.save(update_fields=["profile_photo"])

        # -------------------------------------------------
        # UPLOAD EMPLOYEE DOCUMENTS
        # -------------------------------------------------
        files = request.FILES.getlist("documents")
        uploaded_documents = []

        for file in files:
            file_path = upload_to_s3(
                file=file,
                folder="employees/documents",
            )

            document = EmployeeDocument.objects.create(
                employee=employee,
                title=file.name,
                file=file_path,
                uploaded_by=request.user,
            )

            uploaded_documents.append(
                {
                    "id": document.id,
                    "title": document.title,
                    "file": document.file.name,
                }
            )

        # -------------------------------------------------
        # AUDIT LOG
        # -------------------------------------------------
        log_activity(
            request=request,
            action="CREATE",
            module="EMPLOYEE",
            object_type="Employee",
            object_id=employee.id,
            description=f"Employee {employee.employee_code} created.",
            new_data={
                "employee_code": employee.employee_code,
                "first_name": employee.first_name,
                "middle_name": employee.middle_name,
                "last_name": employee.last_name,
                "date_of_birth": employee.date_of_birth,
                "gender": employee.gender,
                "mobile": employee.mobile,
                "alternate_mobile": employee.alternate_mobile,
                "personal_email": employee.personal_email,
                "address": employee.address,
                "state": employee.state,
                "district": employee.district,
                "taluka": employee.taluka,
                "pincode": employee.pincode,
                "designation": employee.designation,
                "department": employee.department,
                "joining_date": employee.joining_date,
                "employment_status": employee.employment_status,
                "resignation_date": employee.resignation_date,
                "emergency_contact_name": employee.emergency_contact_name,
                "emergency_contact_number": employee.emergency_contact_number,
                "emergency_contact_relation": employee.emergency_contact_relation,
                "profile_photo": profile_photo_path,
                "documents": uploaded_documents,
                "user_id": user.id if user else None,
                "username": user.username if user else None,
                "user_account_created": bool(user),
                "role": user.role.name if user and user.role else None,
                "membership_id": membership.id if membership else None,
            },
        )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------
        return Response(
            {
                "status": True,
                "message": (
                    "Employee and user account created successfully. "
                    "Account credentials will be sent by email."
                    if user
                    else "Employee created successfully."
                ),
                "data": EmployeeDetailSerializer(
                    employee,
                    context={"request": request},
                ).data,
                "user_account": {
                    "created": bool(user),
                    "user_id": user.id if user else None,
                    "username": user.username if user else None,
                    "email": user.email if user else None,
                    "role": user.role.name if user and user.role else None,
                    "membership_id": (
                        membership.id if membership else None
                    ),
                },
            },
            status=status.HTTP_201_CREATED,
        )


# =========================================================
# CREATE USER FOR EXISTING EMPLOYEE
# =========================================================
class EmployeeUserCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        # -------------------------------------------------
        # GET ORGANIZATION
        # -------------------------------------------------
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        denied = require_perm(request, organization, "employee.create_user")
        if denied:
            return denied

        # -------------------------------------------------
        # VALIDATE EMPLOYEE ID
        # -------------------------------------------------
        employee_id = request.data.get("employee_id")

        if not employee_id:
            return Response(
                {
                    "status": False,
                    "message": "employee_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # GET EMPLOYEE IN CURRENT ORGANIZATION
        # -------------------------------------------------
        employee = Employee.objects.filter(
            id=employee_id,
            organization=organization,
            is_active=True,
        ).first()

        if not employee:
            return Response(
                {
                    "status": False,
                    "message": "Active employee not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # -------------------------------------------------
        # CREATE USER ACCOUNT + ROLE + MEMBERSHIP
        # -------------------------------------------------
        user = None
        membership = None

        try:
            user, _generated_password = create_employee_user(employee)

            # Assign the Employee role to the new user.
            employee_role = Role.objects.filter(
                name__iexact="Employee",
                is_active=True,
            ).first()

            if not employee_role:
                raise ValidationError(
                    {
                        "role": (
                            "An active Employee role must exist "
                            "before creating employee user accounts."
                        )
                    }
                )

            user.role = employee_role
            user.save(update_fields=["role"])

            # Create organization membership for the new user.
            membership, _created = (
                OrganizationMembership.objects.update_or_create(
                    organization=organization,
                    user=user,
                    defaults={"is_active": True},
                )
            )

        except ValidationError as exc:
            transaction.set_rollback(True)

            return Response(
                {
                    "status": False,
                    "message": "Unable to create employee user account.",
                    "errors": exc.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # AUDIT LOG
        # -------------------------------------------------
        log_activity(
            request=request,
            action="CREATE",
            module="EMPLOYEE",
            object_type="Employee",
            object_id=employee.id,
            description=(
                f"User account created for employee "
                f"{employee.employee_code}."
            ),
            new_data={
                "employee_id": employee.id,
                "employee_code": employee.employee_code,
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role.name if user.role else None,
                "membership_id": membership.id if membership else None,
            },
        )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------
        return Response(
            {
                "status": True,
                "message": (
                    "Employee user account created successfully. "
                    "Account credentials will be sent by email."
                ),
                "data": {
                    "employee_id": employee.id,
                    "employee_code": employee.employee_code,
                    "user_id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role.name if user.role else None,
                    "membership_id": (
                        membership.id if membership else None
                    ),
                    "account_active": user.is_active,
                },
            },
            status=status.HTTP_201_CREATED,
        )


# =========================================================
# EMPLOYEE LIST
# =========================================================
class EmployeeListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        # inactive_only=true lists people who left (to reactivate them).
        inactive_only = str(request.data.get("inactive_only", "")).strip().lower() in ("true", "1", "yes")

        employees = Employee.objects.filter(
            organization=organization,
            is_active=not inactive_only,
        ).select_related(
            "work_state", "branch", "department_ref", "designation_ref",
            "access_role", "reports_to",
        ).prefetch_related("documents")

        # Scope (batch 2): all (employee.view_all) | team (employee.view_team)
        # | self (own row).
        scope, scope_error = resolve_scope(
            request, organization, request.data.get("scope"),
            team_code="employee.view_team", all_code="employee.view_all",
        )

        if scope_error:
            return scope_error

        employees = scope.filter(employees, "id")

        # -------------------------------------------------
        # FILTERS (batch 1)
        # -------------------------------------------------
        for key, lookup in (
            ("branch_id", "branch_id"),
            ("department_id", "department_ref_id"),
            ("designation_id", "designation_ref_id"),
            ("access_role_id", "access_role_id"),
            ("reports_to_id", "reports_to_id"),
        ):
            value = request.data.get(key)
            if value not in (None, ""):
                try:
                    employees = employees.filter(**{lookup: int(value)})
                except (TypeError, ValueError):
                    return Response(
                        {"status": False, "message": f"{key} must be a number."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        # -------------------------------------------------
        # SEARCH
        # -------------------------------------------------

        search = request.data.get("search")

        if search:

            search = search.strip()

            employees = employees.filter(
                Q(employee_code__icontains=search)
                | Q(first_name__icontains=search)
                | Q(middle_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(mobile__icontains=search)
                | Q(personal_email__icontains=search)
                | Q(department__icontains=search)
                | Q(designation__icontains=search)
            )

        # -------------------------------------------------
        # ORDERING
        # -------------------------------------------------

        employees = employees.order_by("-created_at")

        # -------------------------------------------------
        # SERIALIZE
        # -------------------------------------------------

        serializer = EmployeeListSerializer(
            employees,
            many=True,
            context={"request": request},
        )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        return Response(
            {
                "status": True,
                "message": "Employees fetched successfully.",
                "data": serializer.data,
                "scope_applied": scope.scope,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# EMPLOYEE DETAIL
# =========================================================
class EmployeeDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        employee_id = request.data.get("employee_id")

        if not employee_id:
            return Response(
                {
                    "status": False,
                    "message": "employee_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # GET EMPLOYEE
        # -------------------------------------------------

        employee = Employee.objects.filter(
            id=employee_id,
            organization=organization,
            is_active=True,
        ).first()

        if not employee:
            return Response(
                {
                    "status": False,
                    "message": "Employee not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        scope, _scope_error = resolve_scope(
            request, organization,
            team_code="employee.view_team", all_code="employee.view_all",
        )

        if scope is None or not scope.allows(employee.id):
            return Response(
                {
                    "status": False,
                    "message": "You do not have permission to view this employee.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # -------------------------------------------------
        # SERIALIZE
        # -------------------------------------------------

        serializer = EmployeeDetailSerializer(
            employee,
            context={"request": request},
        )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        return Response(
            {
                "status": True,
                "message": "Employee details fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# UPDATE EMPLOYEE
# =========================================================
class EmployeeUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        denied = require_perm(request, organization, "employee.update")
        if denied:
            return denied

        employee_id = request.data.get("employee_id")

        if not employee_id:
            return Response(
                {
                    "status": False,
                    "message": "employee_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # GET EMPLOYEE
        # -------------------------------------------------

        employee = Employee.objects.filter(
            id=employee_id,
            organization=organization,
            is_active=True,
        ).first()

        if not employee:
            return Response(
                {
                    "status": False,
                    "message": "Employee not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # -------------------------------------------------
        # OLD DATA FOR AUDIT
        # -------------------------------------------------

        old_data = {
            "first_name": employee.first_name,
            "middle_name": employee.middle_name,
            "last_name": employee.last_name,
            "date_of_birth": employee.date_of_birth,
            "gender": employee.gender,
            "mobile": employee.mobile,
            "alternate_mobile": employee.alternate_mobile,
            "personal_email": employee.personal_email,
            "address": employee.address,
            "state": employee.state,
            "district": employee.district,
            "taluka": employee.taluka,
            "pincode": employee.pincode,
            "designation": employee.designation,
            "department": employee.department,
            "joining_date": employee.joining_date,
            "employment_status": employee.employment_status,
            "resignation_date": employee.resignation_date,
            "emergency_contact_name": employee.emergency_contact_name,
            "emergency_contact_number": employee.emergency_contact_number,
            "emergency_contact_relation": employee.emergency_contact_relation,
            "profile_photo": (
                employee.profile_photo.name
                if employee.profile_photo
                else None
            ),
        }

        # -------------------------------------------------
        # VALIDATE EMPLOYEE DATA
        # -------------------------------------------------

        serializer = EmployeeUpdateSerializer(
            employee,
            data=request.data,
            partial=True,
        )

        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Batch 1: branch / department / designation / access role / manager
        org_changes, org_errors = resolve_org_assignments(
            request.data,
            organization,
            employee=employee,
            can_assign_access=has_perm(request, organization, "access.manage"),
        )

        if org_errors:
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": org_errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_data["org_links"] = {
            "branch_id": employee.branch_id,
            "department_id": employee.department_ref_id,
            "designation_id": employee.designation_ref_id,
            "access_role_id": employee.access_role_id,
            "reports_to_id": employee.reports_to_id,
        }

        validated_data = serializer.validated_data
        User = get_user_model()

        # -------------------------------------------------
        # VALIDATE LINKED USER ACCOUNT
        # Only validate fields included in this request.
        # Employees without a linked User need no validation.
        # -------------------------------------------------

        linked_user = employee.user

        if linked_user:
            account_errors = {}

            # Validate email only when personal_email is sent.
            if "personal_email" in validated_data:
                new_email = validated_data["personal_email"]

                if not new_email:
                    account_errors["personal_email"] = [
                        "Email cannot be empty for an employee with a linked User account."
                    ]

                elif User.objects.filter(
                    email__iexact=new_email
                ).exclude(
                    pk=linked_user.pk
                ).exists():
                    account_errors["personal_email"] = [
                        "This email is already associated with another User account."
                    ]

            # Validate mobile only when mobile is sent.
            if "mobile" in validated_data:
                new_mobile = validated_data["mobile"]

                if not new_mobile:
                    account_errors["mobile"] = [
                        "Mobile number cannot be empty for an employee with a linked User account."
                    ]

                elif len(new_mobile) > 15:
                    account_errors["mobile"] = [
                        "Mobile number cannot exceed 15 characters for a linked User account."
                    ]

                elif User.objects.filter(
                    mobile=new_mobile
                ).exclude(
                    pk=linked_user.pk
                ).exists():
                    account_errors["mobile"] = [
                        "This mobile number is already associated with another User account."
                    ]

            if account_errors:
                return Response(
                    {
                        "status": False,
                        "message": "Linked User account validation failed.",
                        "errors": account_errors,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # -------------------------------------------------
        # UPDATE EMPLOYEE
        # -------------------------------------------------

        employee = serializer.save(
            updated_by=request.user,
        )

        apply_org_assignments(
            employee,
            org_changes,
            text_sent={f for f in ("department", "designation") if f in request.data},
        )

        # -------------------------------------------------
        # SYNCHRONIZE LINKED USER
        # Update only fields included in the request.
        # -------------------------------------------------

        linked_user = employee.user

        if linked_user:
            user_fields_to_update = []

            if "first_name" in validated_data:
                linked_user.first_name = employee.first_name
                user_fields_to_update.append("first_name")

            if "last_name" in validated_data:
                linked_user.last_name = employee.last_name
                user_fields_to_update.append("last_name")

            if "mobile" in validated_data:
                linked_user.mobile = employee.mobile
                user_fields_to_update.append("mobile")

            if "personal_email" in validated_data:
                linked_user.email = employee.personal_email
                user_fields_to_update.append("email")

            if user_fields_to_update:
                linked_user.save(
                    update_fields=user_fields_to_update
                )

        # -------------------------------------------------
        # PROFILE PHOTO REPLACEMENT
        # -------------------------------------------------

        old_profile_photo = (
            employee.profile_photo.name
            if employee.profile_photo
            else None
        )

        new_profile_photo = request.FILES.get("profile_photo")
        profile_photo_changed = False

        if new_profile_photo:

            # Delete old profile photo from S3.
            if employee.profile_photo:
                delete_from_s3(employee.profile_photo)

            # Upload replacement profile photo.
            profile_photo_path = upload_to_s3(
                file=new_profile_photo,
                folder="employees/profile",
            )

            employee.profile_photo = profile_photo_path

            employee.save(
                update_fields=[
                    "profile_photo",
                    "updated_by",
                    "updated_at",
                ]
            )

            profile_photo_changed = True

        # -------------------------------------------------
        # REMOVE OLD DOCUMENTS
        # -------------------------------------------------

        # Works for multipart (repeated keys) and JSON (a list).
        if hasattr(request.data, "getlist"):
            remove_document_ids = request.data.getlist("remove_document_ids")
        else:
            remove_document_ids = request.data.get("remove_document_ids") or []
            if not isinstance(remove_document_ids, list):
                remove_document_ids = [remove_document_ids]

        removed_documents = []

        for document_id in remove_document_ids:
            document = EmployeeDocument.objects.filter(
                id=document_id,
                employee=employee,
            ).first()

            if not document:
                continue

            removed_documents.append(
                {
                    "id": document.id,
                    "title": document.title,
                    "file": (
                        document.file.name
                        if document.file
                        else None
                    ),
                }
            )

            # Delete document from S3.
            if document.file:
                delete_from_s3(document.file)

            # Delete database record.
            document.delete()

        # -------------------------------------------------
        # ADD NEW DOCUMENTS
        # -------------------------------------------------

        files = request.FILES.getlist("documents")
        added_documents = []

        for file in files:
            file_path = upload_to_s3(
                file=file,
                folder="employees/documents",
            )

            document = EmployeeDocument.objects.create(
                employee=employee,
                title=file.name,
                file=file_path,
                uploaded_by=request.user,
            )

            added_documents.append(
                {
                    "id": document.id,
                    "title": document.title,
                    "file": document.file.name,
                }
            )

        # -------------------------------------------------
        # NEW DATA FOR AUDIT
        # -------------------------------------------------

        new_data = {
            "first_name": employee.first_name,
            "middle_name": employee.middle_name,
            "last_name": employee.last_name,
            "date_of_birth": employee.date_of_birth,
            "gender": employee.gender,
            "mobile": employee.mobile,
            "alternate_mobile": employee.alternate_mobile,
            "personal_email": employee.personal_email,
            "address": employee.address,
            "state": employee.state,
            "district": employee.district,
            "taluka": employee.taluka,
            "pincode": employee.pincode,
            "designation": employee.designation,
            "department": employee.department,
            "joining_date": employee.joining_date,
            "employment_status": employee.employment_status,
            "resignation_date": employee.resignation_date,
            "emergency_contact_name": employee.emergency_contact_name,
            "emergency_contact_number": employee.emergency_contact_number,
            "emergency_contact_relation": employee.emergency_contact_relation,
            "profile_photo": (
                employee.profile_photo.name
                if employee.profile_photo
                else None
            ),
        }

        new_data["org_links"] = {
            "branch_id": employee.branch_id,
            "department_id": employee.department_ref_id,
            "designation_id": employee.designation_ref_id,
            "access_role_id": employee.access_role_id,
            "reports_to_id": employee.reports_to_id,
        }

        if profile_photo_changed:
            new_data["profile_photo_changed"] = True
            new_data["old_profile_photo"] = old_profile_photo

        if added_documents:
            new_data["documents_added"] = added_documents

        if removed_documents:
            new_data["documents_removed"] = removed_documents

        # -------------------------------------------------
        # AUDIT LOG
        # -------------------------------------------------

        log_activity(
            request=request,
            action="UPDATE",
            module="EMPLOYEE",
            object_type="Employee",
            object_id=employee.id,
            description=f"Employee {employee.employee_code} updated.",
            old_data=old_data,
            new_data=new_data,
        )

        # -------------------------------------------------
        # RESPONSE
        # Existing response structure preserved.
        # -------------------------------------------------

        return Response(
            {
                "status": True,
                "message": "Employee updated successfully.",
                "data": EmployeeDetailSerializer(
                    employee,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# DEACTIVATE EMPLOYEE / SOFT DELETE
# =========================================================
class EmployeeDeactivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        denied = require_perm(request, organization, "employee.update")
        if denied:
            return denied

        employee_id = request.data.get("employee_id")

        if not employee_id:
            return Response(
                {
                    "status": False,
                    "message": "employee_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # GET EMPLOYEE
        # -------------------------------------------------

        employee = Employee.objects.filter(
            id=employee_id,
            organization=organization,
            is_active=True,
        ).first()

        if not employee:
            return Response(
                {
                    "status": False,
                    "message": "Employee not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # -------------------------------------------------
        # OLD DATA
        # -------------------------------------------------

        old_data = {
            "is_active": employee.is_active,
            "employment_status": employee.employment_status,
        }

        # -------------------------------------------------
        # SOFT DELETE
        # -------------------------------------------------

        # Batch 4: last working day closes open shift / salary assignments.
        from datetime import date as _date
        from django.utils import timezone as _tz

        raw_lwd = request.data.get("last_working_day")
        try:
            last_working_day = (
                _date.fromisoformat(str(raw_lwd)) if raw_lwd
                else (employee.resignation_date or _tz.localdate())
            )
        except ValueError:
            return Response(
                {"status": False, "message": "last_working_day must use YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        closed = close_open_assignments(employee, last_working_day)

        employee.is_active = False
        employee.employment_status = "INACTIVE"
        employee.updated_by = request.user

        employee.save(
            update_fields=[
                "is_active",
                "employment_status",
                "updated_by",
                "updated_at",
            ]
        )

        # -------------------------------------------------
        # LOGIN: organization membership off; the user account is
        # deactivated when no other active organization is left
        # (owners and super admins are never touched).
        # -------------------------------------------------
        login_disabled = False
        user = employee.user
        if user is not None and organization.owner_id != user.id and not is_super_admin(user):
            OrganizationMembership.objects.filter(
                organization=organization, user=user, is_active=True,
            ).update(is_active=False)
            still_member = OrganizationMembership.objects.filter(
                user=user, is_active=True, organization__is_active=True,
            ).exists()
            if not still_member and user.is_active:
                user.is_active = False
                user.save(update_fields=["is_active"])
                login_disabled = True

        # Assets still with the employee (information only; exit is not blocked).
        from app.assets.models import Asset

        assets_held = [
            {"id": a.id, "asset_code": a.asset_code, "name": a.name}
            for a in Asset.objects.filter(
                organization=organization, current_holder=employee, status="ASSIGNED", is_active=True,
            ).order_by("name")
        ]

        # -------------------------------------------------
        # AUDIT LOG
        # -------------------------------------------------

        log_activity(
            request=request,
            action="DELETE",
            module="EMPLOYEE",
            object_type="Employee",
            object_id=employee.id,
            description=f"Employee {employee.employee_code} deactivated.",
            old_data=old_data,
            new_data={
                "is_active": False,
                "employment_status": "INACTIVE",
                "last_working_day": str(last_working_day),
                **closed,
            },
        )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        return Response(
            {
                "status": True,
                "message": "Employee deactivated successfully.",
                "data": {
                    "last_working_day": str(last_working_day),
                    **closed,
                    "login_disabled": login_disabled,
                    "assets_held": assets_held,
                },
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# UPLOAD EMPLOYEE DOCUMENT
# =========================================================
class EmployeeDocumentUploadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        denied = require_perm(request, organization, "employee.update")
        if denied:
            return denied

        employee_id = request.data.get("employee_id")

        if not employee_id:
            return Response(
                {
                    "status": False,
                    "message": "employee_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # GET EMPLOYEE
        # -------------------------------------------------

        employee = Employee.objects.filter(
            id=employee_id,
            organization=organization,
            is_active=True,
        ).first()

        if not employee:
            return Response(
                {
                    "status": False,
                    "message": "Employee not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # -------------------------------------------------
        # GET FILE
        # -------------------------------------------------

        file = request.FILES.get("file")

        if not file:
            return Response(
                {
                    "status": False,
                    "message": "file is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # TITLE / DESCRIPTION
        # -------------------------------------------------

        title = request.data.get("title")

        if not title:
            title = file.name

        description = request.data.get("description")

        # -------------------------------------------------
        # UPLOAD TO S3
        # -------------------------------------------------

        file_path = upload_to_s3(
            file=file,
            folder="employees/documents",
        )

        # -------------------------------------------------
        # CREATE DOCUMENT
        # -------------------------------------------------

        document = EmployeeDocument.objects.create(
            employee=employee,
            title=title,
            file=file_path,
            description=description,
            uploaded_by=request.user,
        )

        # -------------------------------------------------
        # AUDIT LOG
        # -------------------------------------------------

        log_activity(
            request=request,
            action="UPLOAD",
            module="EMPLOYEE",
            object_type="EmployeeDocument",
            object_id=document.id,
            description=(
                f"Document uploaded for employee "
                f"{employee.employee_code}."
            ),
            new_data={
                "employee_id": employee.id,
                "employee_code": employee.employee_code,
                "document_id": document.id,
                "title": document.title,
                "file": document.file.name
                if document.file
                else None,
                "description": document.description,
            },
        )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        return Response(
            {
                "status": True,
                "message": "Employee document uploaded successfully.",
                "data": {
                    "id": document.id,
                    "title": document.title,
                    "file": document.file.name
                    if document.file
                    else None,
                    "description": document.description,
                    "created_at": document.created_at,
                },
            },
            status=status.HTTP_201_CREATED,
        )


# =========================================================
# DELETE EMPLOYEE DOCUMENT
# =========================================================
class EmployeeDocumentDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        denied = require_perm(request, organization, "employee.update")
        if denied:
            return denied

        document_id = request.data.get("document_id")

        if not document_id:
            return Response(
                {
                    "status": False,
                    "message": "document_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -------------------------------------------------
        # GET DOCUMENT
        # -------------------------------------------------

        document = EmployeeDocument.objects.filter(
            id=document_id,
            employee__organization=organization,
            employee__is_active=True,
        ).select_related("employee").first()

        if not document:
            return Response(
                {
                    "status": False,
                    "message": "Employee document not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # -------------------------------------------------
        # OLD DATA FOR AUDIT
        # -------------------------------------------------

        old_data = {
            "employee_id": document.employee.id,
            "employee_code": document.employee.employee_code,
            "document_id": document.id,
            "title": document.title,
            "file": document.file.name
            if document.file
            else None,
            "description": document.description,
        }

        employee_code = document.employee.employee_code

        # -------------------------------------------------
        # DELETE FROM S3
        # -------------------------------------------------

        if document.file:
            delete_from_s3(document.file)

        # -------------------------------------------------
        # DELETE DATABASE RECORD
        # -------------------------------------------------

        document.delete()

        # -------------------------------------------------
        # AUDIT LOG
        # -------------------------------------------------

        log_activity(
            request=request,
            action="DELETE",
            module="EMPLOYEE",
            object_type="EmployeeDocument",
            object_id=document_id,
            description=(
                f"Document deleted from employee "
                f"{employee_code}."
            ),
            old_data=old_data,
            new_data=None,
        )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        return Response(
            {
                "status": True,
                "message": "Employee document deleted successfully.",
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# MY EMPLOYEE PROFILE (employee self-service)
# =========================================================
class MyEmployeeProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        employee, error_response = get_current_employee(request)
        if error_response:
            return error_response

        # Refresh from DB to include prefetched relations cleanly.
        employee = (
            Employee.objects
            .filter(id=employee.id, is_active=True)
            .select_related("work_state", "organization")
            .prefetch_related("documents")
            .first()
        )

        if not employee:
            return Response(
                {
                    "status": False,
                    "message": "Your employee profile is no longer active.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = MyEmployeeProfileSerializer(
            employee,
            context={"request": request},
        )

        log_activity(
            request=request,
            action="VIEW",
            module="EMPLOYEE",
            object_type="Employee",
            object_id=employee.id,
            description=(
                f"Employee {employee.employee_code} viewed their own profile."
            ),
        )

        return Response(
            {
                "status": True,
                "message": "Your profile fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# =========================================================
# DEPARTMENT / DESIGNATION MASTERS (per organization)
# list = any member; create / update / deactivate = org.manage
# =========================================================
# =========================================================
class _MasterBase(OrgAPIView):
    model = None
    read_serializer = None
    write_serializer = None
    id_field = None       # "department_id"
    label = None          # "Department"
    module = None         # "DEPARTMENT"
    search_fields = ("name",)

    def queryset(self, organization):
        return self.model.objects.filter(organization=organization).annotate(
            employee_count=Count("employees", filter=Q(employees__is_active=True), distinct=True)
        )

    def serialize(self, organization, pk):
        return self.read_serializer(self.queryset(organization).get(pk=pk)).data


class _MasterList(_MasterBase):
    def post(self, request):
        organization, error = get_user_organization(request)
        if error:
            return error
        qs = self.queryset(organization)
        search = (request.data.get("search") or "").strip()
        if search:
            q = Q()
            for f in self.search_fields:
                q |= Q(**{f"{f}__icontains": search})
            qs = qs.filter(q)
        is_active = self.parse_bool(request.data.get("is_active"))
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        return self.ok(f"{self.label}s fetched successfully.",
                       self.read_serializer(qs.order_by("name"), many=True).data)


class _MasterCreate(_MasterBase):
    @transaction.atomic
    def post(self, request):
        organization, error = get_user_organization(request)
        if error:
            return error
        denied = require_perm(request, organization, "org.manage")
        if denied:
            return denied
        serializer = self.write_serializer(data=request.data, context={"organization": organization})
        if not serializer.is_valid():
            return self.fail("Validation failed.", serializer.errors)
        obj = serializer.save(organization=organization, created_by=request.user, updated_by=request.user)
        data = self.serialize(organization, obj.pk)
        log_activity(request=request, action="CREATE", module=self.module, object_type=self.model.__name__,
                     object_id=obj.id, description=f"{self.label} '{obj.name}' created.", new_data=data)
        return self.ok(f"{self.label} created successfully.", data, status.HTTP_201_CREATED)


class _MasterUpdate(_MasterBase):
    @transaction.atomic
    def post(self, request):
        organization, error = get_user_organization(request)
        if error:
            return error
        denied = require_perm(request, organization, "org.manage")
        if denied:
            return denied
        pk = request.data.get(self.id_field)
        if not pk:
            return self.fail(f"{self.id_field} is required.")
        obj = self.model.objects.filter(pk=pk, organization=organization).first()
        if not obj:
            return self.fail(f"{self.label} not found.", http_status=status.HTTP_404_NOT_FOUND)

        old = self.serialize(organization, obj.pk)
        serializer = self.write_serializer(obj, data=request.data, partial=True,
                                           context={"organization": organization})
        if not serializer.is_valid():
            return self.fail("Validation failed.", serializer.errors)
        obj = serializer.save(updated_by=request.user)

        # Keep the legacy text field on linked employees in step with a rename.
        if "name" in serializer.validated_data and old["name"] != obj.name:
            text_field = "department" if self.model is Department else "designation"
            obj.employees.update(**{text_field: obj.name})

        data = self.serialize(organization, obj.pk)
        log_activity(request=request, action="UPDATE", module=self.module, object_type=self.model.__name__,
                     object_id=obj.id, description=f"{self.label} '{obj.name}' updated.",
                     old_data=old, new_data=data)
        return self.ok(f"{self.label} updated successfully.", data)


class _MasterDeactivate(_MasterBase):
    @transaction.atomic
    def post(self, request):
        organization, error = get_user_organization(request)
        if error:
            return error
        denied = require_perm(request, organization, "org.manage")
        if denied:
            return denied
        pk = request.data.get(self.id_field)
        if not pk:
            return self.fail(f"{self.id_field} is required.")
        obj = self.model.objects.filter(pk=pk, organization=organization, is_active=True).first()
        if not obj:
            return self.fail(f"Active {self.label.lower()} not found.", http_status=status.HTTP_404_NOT_FOUND)
        in_use = obj.employees.filter(is_active=True).count()
        if in_use:
            return self.fail(f"This {self.label.lower()} is assigned to {in_use} active employee(s). Reassign them first.")
        obj.is_active = False
        obj.updated_by = request.user
        obj.save(update_fields=["is_active", "updated_by", "updated_at"])
        log_activity(request=request, action="DELETE", module=self.module, object_type=self.model.__name__,
                     object_id=obj.id, description=f"{self.label} '{obj.name}' deactivated.",
                     old_data={"is_active": True}, new_data={"is_active": False})
        return self.ok(f"{self.label} deactivated successfully.", {"id": obj.id, "is_active": False})


_DEPT = dict(model=Department, read_serializer=DepartmentSerializer, write_serializer=DepartmentWriteSerializer,
             id_field="department_id", label="Department", module="DEPARTMENT", search_fields=("name", "code"))
_DESIG = dict(model=Designation, read_serializer=DesignationSerializer, write_serializer=DesignationWriteSerializer,
              id_field="designation_id", label="Designation", module="DESIGNATION")

DepartmentListAPIView = type("DepartmentListAPIView", (_MasterList,), _DEPT)
DepartmentCreateAPIView = type("DepartmentCreateAPIView", (_MasterCreate,), _DEPT)
DepartmentUpdateAPIView = type("DepartmentUpdateAPIView", (_MasterUpdate,), _DEPT)
DepartmentDeactivateAPIView = type("DepartmentDeactivateAPIView", (_MasterDeactivate,), _DEPT)

DesignationListAPIView = type("DesignationListAPIView", (_MasterList,), _DESIG)
DesignationCreateAPIView = type("DesignationCreateAPIView", (_MasterCreate,), _DESIG)
DesignationUpdateAPIView = type("DesignationUpdateAPIView", (_MasterUpdate,), _DESIG)
DesignationDeactivateAPIView = type("DesignationDeactivateAPIView", (_MasterDeactivate,), _DESIG)


# =========================================================
# EMPLOYEE REACTIVATE (rehire) — mirror of deactivate
# =========================================================
class EmployeeReactivateAPIView(APIView):
    """
    Brings a deactivated employee back: same record, same history, same login.
    Shift and salary are not restored; assign them again like for a joiner.
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        from datetime import date as _date

        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        denied = require_perm(request, organization, "employee.update")
        if denied:
            return denied

        employee_id = request.data.get("employee_id")

        if not employee_id:
            return Response(
                {"status": False, "message": "employee_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        employee = Employee.objects.filter(
            id=employee_id,
            organization=organization,
            is_active=False,
        ).select_related("user").first()

        if not employee:
            return Response(
                {"status": False, "message": "Inactive employee not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        raw_joining = request.data.get("joining_date")
        try:
            joining_date = _date.fromisoformat(str(raw_joining)) if raw_joining else None
        except ValueError:
            return Response(
                {"status": False, "message": "joining_date must use YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_data = {
            "is_active": employee.is_active,
            "employment_status": employee.employment_status,
            "joining_date": str(employee.joining_date) if employee.joining_date else None,
            "resignation_date": str(employee.resignation_date) if employee.resignation_date else None,
        }

        # -------------------------------------------------
        # EMPLOYEE BACK TO ACTIVE
        # -------------------------------------------------
        employee.is_active = True
        employee.employment_status = "ACTIVE"
        employee.resignation_date = None
        fields = ["is_active", "employment_status", "resignation_date", "updated_by", "updated_at"]
        if joining_date:
            employee.joining_date = joining_date
            fields.append("joining_date")
        employee.updated_by = request.user
        employee.save(update_fields=fields)

        # -------------------------------------------------
        # LOGIN BACK ON (membership + user account)
        # -------------------------------------------------
        login_enabled = False
        user = employee.user
        if user is not None:
            OrganizationMembership.objects.update_or_create(
                organization=organization,
                user=user,
                defaults={"is_active": True},
            )
            if not user.is_active:
                user.is_active = True
                user.save(update_fields=["is_active"])
            login_enabled = True

        log_activity(
            request=request,
            action="UPDATE",
            module="EMPLOYEE",
            object_type="Employee",
            object_id=employee.id,
            description=f"Employee {employee.employee_code} reactivated.",
            old_data=old_data,
            new_data={
                "is_active": True,
                "employment_status": "ACTIVE",
                "joining_date": str(employee.joining_date) if employee.joining_date else None,
            },
        )

        return Response(
            {
                "status": True,
                "message": "Employee reactivated successfully.",
                "data": {
                    "employee_id": employee.id,
                    "employee_code": employee.employee_code,
                    "joining_date": str(employee.joining_date) if employee.joining_date else None,
                    "login_enabled": login_enabled,
                    "has_login": user is not None,
                    "next_steps": [
                        "Assign a shift (attendance).",
                        "Assign a salary structure (payroll).",
                    ],
                },
            },
            status=status.HTTP_200_OK,
        )
