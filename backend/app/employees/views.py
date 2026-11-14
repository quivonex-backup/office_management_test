from django.db import transaction
from django.db.models import Q
from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError

from .models import Employee, EmployeeDocument
from app.accounts.models import Role, OrganizationMembership

from .serializers import (
    EmployeeCreateSerializer,
    EmployeeListSerializer,
    EmployeeDetailSerializer,
    EmployeeUpdateSerializer,
)

from common.services import get_user_organization
from common.s3_utils import upload_to_s3, delete_from_s3
from app.audit.services import log_activity
from .services import create_employee_user




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

        employees = Employee.objects.filter(
            organization=organization,
            is_active=True,
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

        remove_document_ids = request.data.getlist(
            "remove_document_ids"
        )

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
            },
        )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        return Response(
            {
                "status": True,
                "message": "Employee deactivated successfully.",
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