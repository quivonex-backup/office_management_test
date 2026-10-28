from django.db import transaction
from django.db.models import Q

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Project, ProjectDocument, ProjectTeamAllocation
from .serializers import (
    ProjectCreateSerializer,
    ProjectListSerializer,
    ProjectDetailSerializer,
    ProjectUpdateSerializer,

    ProjectTeamAllocationSerializer,
    ProjectTeamAllocationListSerializer,
    ProjectTeamAllocationDetailSerializer,
    ProjectTeamProjectSerializer,
    ProjectTeamEmployeeSerializer,
)
from common.services import get_user_organization
from common.s3_utils import upload_to_s3, delete_from_s3
from common.code_generators import generate_project_code
from app.audit.services import log_activity



# =========================================================
# CREATE PROJECT
# =========================================================
class ProjectCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        data = request.data.copy()
        data.pop("organization_id", None)

        serializer = ProjectCreateSerializer(data=data)

        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = serializer.validated_data.get("client")

        if not client or client.organization_id != organization.id:
            return Response(
                {
                    "status": False,
                    "message": (
                        "Selected client does not belong to "
                        "this organization."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = serializer.save(
            organization=organization,
            created_by=request.user,
            updated_by=request.user,
        )

        project.project_code = generate_project_code()
        project.save(update_fields=["project_code", "updated_at"])

        files = request.FILES.getlist("documents")
        uploaded_documents = []

        for file in files:
            file_path = upload_to_s3(
                file=file,
                folder="projects/documents",
            )

            document = ProjectDocument.objects.create(
                project=project,
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

        log_activity(
            request=request,
            action="CREATE",
            module="PROJECT",
            object_type="Project",
            object_id=project.id,
            description=f"Project {project.project_name} created.",
            new_data={
                "project_name": project.project_name,
                "client": project.client_id,
                "organization_id": organization.id,
                "project_type": project.project_type,
                "description": project.description,
                "start_date": project.start_date,
                "end_date": project.end_date,
                "deadline": project.deadline,
                "priority": project.priority,
                "status": project.status,
                "total_cost": project.total_cost,
                "live_url": project.live_url,
                "documents": uploaded_documents,
            },
        )

        return Response(
            {
                "status": True,
                "message": "Project created successfully.",
                "data": ProjectDetailSerializer(
                    project,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


# =========================================================
# PROJECT LIST
# =========================================================
class ProjectListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)

        if error_response:
            return error_response

        projects = (
            Project.objects.filter(
                organization=organization,
                is_active=True,
            )
            .select_related("client")
            .prefetch_related("documents")
        )

        search = request.data.get("search")

        if search:
            search = search.strip()
            projects = projects.filter(
                Q(project_name__icontains=search)
                | Q(project_type__icontains=search)
                | Q(client__client_name__icontains=search)
            )

        client_id = request.data.get("client_id")
        project_status = request.data.get("status")
        priority = request.data.get("priority")

        if client_id:
            projects = projects.filter(client_id=client_id)

        if project_status:
            projects = projects.filter(status=project_status)

        if priority:
            projects = projects.filter(priority=priority)

        projects = projects.order_by("-created_at")

        serializer = ProjectListSerializer(
            projects,
            many=True,
            context={"request": request},
        )

        return Response(
            {
                "status": True,
                "message": "Projects fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# PROJECT DETAIL
# =========================================================
class ProjectDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        project_id = request.data.get("project_id")

        if not project_id:
            return Response(
                {
                    "status": False,
                    "message": "project_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = (
            Project.objects
            .filter(
                id=project_id,
                organization=organization,
                is_active=True,
            )
            .select_related("client")
            .prefetch_related("documents")
            .first()
        )

        if not project:
            return Response(
                {
                    "status": False,
                    "message": "Project not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProjectDetailSerializer(
            project,
            context={"request": request}
        )

        return Response(
            {
                "status": True,
                "message": "Project details fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# UPDATE PROJECT
# =========================================================
class ProjectUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        project_id = request.data.get("project_id")

        if not project_id:
            return Response(
                {
                    "status": False,
                    "message": "project_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = (
            Project.objects
            .filter(
                id=project_id,
                organization=organization,
                is_active=True,
            )
            .first()
        )

        if not project:
            return Response(
                {
                    "status": False,
                    "message": "Project not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        old_data = {
            "project_name": project.project_name,
            "client": project.client_id,
            "project_type": project.project_type,
            "description": project.description,
            "start_date": project.start_date,
            "end_date": project.end_date,
            "deadline": project.deadline,
            "priority": project.priority,
            "status": project.status,
            "total_cost": project.total_cost,
            "live_url": project.live_url,
        }

        serializer = ProjectUpdateSerializer(
            project,
            data=request.data,
            partial=True
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

        project = serializer.save(updated_by=request.user)

        remove_document_ids = request.data.getlist("remove_document_ids")
        removed_documents = []

        for document_id in remove_document_ids:
            document = ProjectDocument.objects.filter(
                id=document_id,
                project=project
            ).first()

            if not document:
                continue

            removed_documents.append({
                "id": document.id,
                "title": document.title,
                "file": document.file.name if document.file else None,
            })

            if document.file:
                delete_from_s3(document.file)

            document.delete()

        files = request.FILES.getlist("documents")
        added_documents = []

        for file in files:
            file_path = upload_to_s3(
                file=file,
                folder="projects/documents"
            )

            document = ProjectDocument.objects.create(
                project=project,
                title=file.name,
                file=file_path,
                uploaded_by=request.user,
            )

            added_documents.append({
                "id": document.id,
                "title": document.title,
                "file": document.file.name,
            })

        new_data = {
            "project_name": project.project_name,
            "client": project.client_id,
            "project_type": project.project_type,
            "description": project.description,
            "start_date": project.start_date,
            "end_date": project.end_date,
            "deadline": project.deadline,
            "priority": project.priority,
            "status": project.status,
            "total_cost": project.total_cost,
            "live_url": project.live_url,
        }

        if added_documents:
            new_data["documents_added"] = added_documents

        if removed_documents:
            new_data["documents_removed"] = removed_documents

        log_activity(
            request=request,
            action="UPDATE",
            module="PROJECT",
            object_type="Project",
            object_id=project.id,
            description=f"Project {project.project_name} updated.",
            old_data=old_data,
            new_data=new_data,
        )

        return Response(
            {
                "status": True,
                "message": "Project updated successfully.",
                "data": ProjectDetailSerializer(
                    project,
                    context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# DEACTIVATE PROJECT / SOFT DELETE
# =========================================================
class ProjectDeactivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        project_id = request.data.get("project_id")

        if not project_id:
            return Response(
                {
                    "status": False,
                    "message": "project_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = Project.objects.filter(
            id=project_id,
            organization=organization,
            is_active=True,
        ).first()

        if not project:
            return Response(
                {
                    "status": False,
                    "message": "Project not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        old_data = {
            "is_active": project.is_active
        }

        project.is_active = False
        project.updated_by = request.user

        project.save(
            update_fields=[
                "is_active",
                "updated_by",
                "updated_at",
            ]
        )

        log_activity(
            request=request,
            action="DELETE",
            module="PROJECT",
            object_type="Project",
            object_id=project.id,
            description=f"Project {project.project_name} deactivated.",
            old_data=old_data,
            new_data={
                "is_active": False
            },
        )

        return Response(
            {
                "status": True,
                "message": "Project deactivated successfully.",
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# CREATE PROJECT TEAM ALLOCATION
# =========================================================
class ProjectTeamAllocationCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = ProjectTeamAllocationSerializer(
            data=request.data
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

        allocation = serializer.save(
            allocated_by=request.user
        )

        log_activity(
            request=request,
            action="CREATE",
            module="PROJECT_TEAM",
            object_type="ProjectTeamAllocation",
            object_id=allocation.id,
            description=(
                f"Employee "
                f"{allocation.employee.employee_code} "
                f"allocated to project "
                f"{allocation.project.project_name}."
            ),
            new_data={
                "project": allocation.project_id,
                "employee": allocation.employee_id,
                "project_role": allocation.project_role,
                "allocation_percentage": allocation.allocation_percentage,
                "start_date": allocation.start_date,
                "end_date": allocation.end_date,
                "notes": allocation.notes,
                "is_active": allocation.is_active,
            },
        )

        return Response(
            {
                "status": True,
                "message": (
                    "Employee allocated to project "
                    "successfully."
                ),
                "data": ProjectTeamAllocationDetailSerializer(
                    allocation,
                    context={"request": request}
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


# =========================================================
# PROJECT TEAM ALLOCATION LIST
# =========================================================
class ProjectTeamAllocationListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        allocations = (
            ProjectTeamAllocation.objects
            .filter(
                project__organization=organization,
                is_active=True,
            )
            .select_related(
                "project",
                "project__client",
                "employee",
                "allocated_by",
            )
        )

        search = request.data.get("search")

        if search:
            search = search.strip()
            allocations = allocations.filter(
                Q(project__project_name__icontains=search)
                | Q(project__project_type__icontains=search)
                | Q(employee__employee_code__icontains=search)
                | Q(employee__first_name__icontains=search)
                | Q(employee__middle_name__icontains=search)
                | Q(employee__last_name__icontains=search)
                | Q(project_role__icontains=search)
            )

        project_id = request.data.get("project_id")
        employee_id = request.data.get("employee_id")
        allocation_status = request.data.get("is_active")
        project_role = request.data.get("project_role")

        if project_id:
            allocations = allocations.filter(
                project_id=project_id
            )

        if employee_id:
            allocations = allocations.filter(
                employee_id=employee_id
            )

        if allocation_status is not None:
            if isinstance(allocation_status, str):
                allocation_status = (
                    allocation_status.lower()
                    in ["true", "1", "yes"]
                )
            allocations = allocations.filter(
                is_active=allocation_status
            )

        if project_role:
            allocations = allocations.filter(
                project_role__icontains=project_role.strip()
            )

        allocations = allocations.order_by(
            "-created_at"
        )

        serializer = ProjectTeamAllocationListSerializer(
            allocations,
            many=True,
            context={"request": request}
        )

        return Response(
            {
                "status": True,
                "message": (
                    "Project team allocations "
                    "fetched successfully."
                ),
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# PROJECT TEAM ALLOCATION DETAIL
# =========================================================
class ProjectTeamAllocationDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        allocation_id = request.data.get("allocation_id")

        if not allocation_id:
            return Response(
                {
                    "status": False,
                    "message": "allocation_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        allocation = (
            ProjectTeamAllocation.objects
            .filter(
                id=allocation_id,
                project__organization=organization,
            )
            .select_related(
                "project",
                "project__client",
                "employee",
                "allocated_by",
            )
            .first()
        )

        if not allocation:
            return Response(
                {
                    "status": False,
                    "message": (
                        "Project team allocation "
                        "not found."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ProjectTeamAllocationDetailSerializer(
            allocation,
            context={"request": request}
        )

        log_activity(
            request=request,
            action="VIEW",
            module="PROJECT_TEAM",
            object_type="ProjectTeamAllocation",
            object_id=allocation.id,
            description=(
                f"Project team allocation "
                f"{allocation.id} viewed."
            ),
        )

        return Response(
            {
                "status": True,
                "message": (
                    "Project team allocation details "
                    "fetched successfully."
                ),
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# UPDATE PROJECT TEAM ALLOCATION
# =========================================================
class ProjectTeamAllocationUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        allocation_id = request.data.get("allocation_id")

        if not allocation_id:
            return Response(
                {
                    "status": False,
                    "message": "allocation_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        allocation = (
            ProjectTeamAllocation.objects
            .filter(
                id=allocation_id,
                project__organization=organization,
                is_active=True,
            )
            .select_related(
                "project",
                "employee",
            )
            .first()
        )

        if not allocation:
            return Response(
                {
                    "status": False,
                    "message": (
                        "Project team allocation "
                        "not found."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        old_data = {
            "project": allocation.project_id,
            "employee": allocation.employee_id,
            "project_role": allocation.project_role,
            "allocation_percentage": allocation.allocation_percentage,
            "start_date": allocation.start_date,
            "end_date": allocation.end_date,
            "notes": allocation.notes,
            "is_active": allocation.is_active,
        }

        serializer = ProjectTeamAllocationSerializer(
            allocation,
            data=request.data,
            partial=True
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

        allocation = serializer.save(
            allocated_by=request.user
        )

        new_data = {
            "project": allocation.project_id,
            "employee": allocation.employee_id,
            "project_role": allocation.project_role,
            "allocation_percentage": allocation.allocation_percentage,
            "start_date": allocation.start_date,
            "end_date": allocation.end_date,
            "notes": allocation.notes,
            "is_active": allocation.is_active,
        }

        log_activity(
            request=request,
            action="UPDATE",
            module="PROJECT_TEAM",
            object_type="ProjectTeamAllocation",
            object_id=allocation.id,
            description=(
                f"Project team allocation "
                f"{allocation.id} updated."
            ),
            old_data=old_data,
            new_data=new_data,
        )

        return Response(
            {
                "status": True,
                "message": (
                    "Project team allocation "
                    "updated successfully."
                ),
                "data": ProjectTeamAllocationDetailSerializer(
                    allocation,
                    context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# DEACTIVATE PROJECT TEAM ALLOCATION
# =========================================================
class ProjectTeamAllocationDeactivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        allocation_id = request.data.get("allocation_id")

        if not allocation_id:
            return Response(
                {
                    "status": False,
                    "message": "allocation_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        allocation = (
            ProjectTeamAllocation.objects
            .filter(
                id=allocation_id,
                project__organization=organization,
                is_active=True,
            )
            .select_related(
                "project",
                "employee",
            )
            .first()
        )

        if not allocation:
            return Response(
                {
                    "status": False,
                    "message": (
                        "Active project team allocation "
                        "not found."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        old_data = {
            "project": allocation.project_id,
            "employee": allocation.employee_id,
            "project_role": allocation.project_role,
            "allocation_percentage": allocation.allocation_percentage,
            "start_date": allocation.start_date,
            "end_date": allocation.end_date,
            "notes": allocation.notes,
            "is_active": allocation.is_active,
        }

        allocation.is_active = False
        allocation.save(
            update_fields=[
                "is_active",
                "updated_at",
            ]
        )

        log_activity(
            request=request,
            action="DELETE",
            module="PROJECT_TEAM",
            object_type="ProjectTeamAllocation",
            object_id=allocation.id,
            description=(
                f"Employee "
                f"{allocation.employee.employee_code} "
                f"removed from project "
                f"{allocation.project.project_name}."
            ),
            old_data=old_data,
            new_data={
                "project": allocation.project_id,
                "employee": allocation.employee_id,
                "project_role": allocation.project_role,
                "allocation_percentage": allocation.allocation_percentage,
                "start_date": allocation.start_date,
                "end_date": allocation.end_date,
                "notes": allocation.notes,
                "is_active": allocation.is_active,
            },
        )

        return Response(
            {
                "status": True,
                "message": (
                    "Employee removed from project "
                    "successfully."
                ),
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# PROJECT TEAM
# =========================================================
class ProjectTeamAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        project_id = request.data.get("project_id")

        if not project_id:
            return Response(
                {
                    "status": False,
                    "message": "project_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = (
            Project.objects
            .filter(
                id=project_id,
                organization=organization,
                is_active=True,
            )
            .select_related("client")
            .first()
        )

        if not project:
            return Response(
                {
                    "status": False,
                    "message": "Project not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        allocations = (
            ProjectTeamAllocation.objects
            .filter(
                project=project,
                is_active=True,
            )
            .select_related(
                "project",
                "employee",
            )
            .order_by("-created_at")
        )

        serializer = ProjectTeamProjectSerializer(
            allocations,
            many=True,
            context={"request": request}
        )

        log_activity(
            request=request,
            action="VIEW",
            module="PROJECT_TEAM",
            object_type="Project",
            object_id=project.id,
            description=(
                f"Project team for "
                f"{project.project_name} viewed."
            ),
        )

        return Response(
            {
                "status": True,
                "message": (
                    "Project team fetched successfully."
                ),
                "data": {
                    "project": {
                        "id": project.id,
                        "project_name": project.project_name,
                        "client_id": project.client_id,
                        "client_name": (
                            project.client.client_name
                            if project.client
                            else None
                        ),
                        "status": project.status,
                        "priority": project.priority,
                    },
                    "team_count": allocations.count(),
                    "team": serializer.data,
                },
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# EMPLOYEE PROJECTS
# =========================================================
class EmployeeProjectsAPIView(APIView):
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

        from app.employees.models import Employee

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

        allocations = (
            ProjectTeamAllocation.objects
            .filter(
                employee=employee,
                project__organization=organization,
                is_active=True,
                project__is_active=True,
            )
            .select_related(
                "project",
                "project__client",
                "employee",
            )
            .order_by("-created_at")
        )

        serializer = ProjectTeamEmployeeSerializer(
            allocations,
            many=True,
            context={"request": request}
        )

        employee_name = (
            f"{employee.first_name} "
            f"{employee.middle_name or ''} "
            f"{employee.last_name}"
        ).replace("  ", " ").strip()

        log_activity(
            request=request,
            action="VIEW",
            module="PROJECT_TEAM",
            object_type="Employee",
            object_id=employee.id,
            description=(
                f"Projects of employee "
                f"{employee.employee_code} viewed."
            ),
        )

        return Response(
            {
                "status": True,
                "message": (
                    "Employee projects fetched "
                    "successfully."
                ),
                "data": {
                    "employee": {
                        "id": employee.id,
                        "employee_code": employee.employee_code,
                        "name": employee_name,
                        "designation": employee.designation,
                        "department": employee.department,
                    },
                    "project_count": allocations.count(),
                    "projects": serializer.data,
                },
            },
            status=status.HTTP_200_OK,
        )