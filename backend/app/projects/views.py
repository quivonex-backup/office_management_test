from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Project, ProjectDocument, ProjectTeamAllocation, Task
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

    TaskCreateSerializer,
    TaskUpdateSerializer,
    TaskStatusUpdateSerializer,
    TaskListSerializer,
    TaskDetailSerializer,
    TaskEmployeeSerializer,
    MyProjectDetailSerializer,
)
from common.services import (
    get_user_organization,
    get_current_employee,
    get_project_permission,
    get_accessible_projects,
)
from common.s3_utils import upload_to_s3, delete_from_s3
from common.code_generators import generate_project_code
from app.communications.notification_service import notify
from app.audit.services import log_activity



def _get_project_notification_recipients(project, organization):
    recipients = []
    seen_user_ids = set()

    if organization.owner_id and organization.owner and organization.owner.is_active:
        recipients.append(organization.owner)
        seen_user_ids.add(organization.owner_id)

    head_allocations = project.team_allocations.filter(
        is_project_head=True,
        is_active=True,
    ).select_related("employee__user")

    for alloc in head_allocations:
        emp = alloc.employee
        if emp.user_id and emp.user_id not in seen_user_ids:
            if emp.user and emp.user.is_active:
                recipients.append(emp.user)
                seen_user_ids.add(emp.user_id)

    return recipients


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
            .prefetch_related("documents", "team_allocations__employee")
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

        new_client = serializer.validated_data.get("client")
        if new_client and new_client.organization_id != organization.id:
            return Response(
                {
                    "status": False,
                    "message": "Selected client does not belong to this organization.",
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
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        from app.employees.models import Employee

        project_id = request.data.get("project")
        employee_id = request.data.get("employee")

        project = (
            Project.objects.filter(
                id=project_id,
                organization=organization,
                is_active=True,
            ).first()
            if project_id else None
        )
        if project_id and not project:
            return Response(
                {
                    "status": False,
                    "message": "Project not found in your organization.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        employee = (
            Employee.objects.filter(
                id=employee_id,
                organization=organization,
                is_active=True,
            ).first()
            if employee_id else None
        )
        if employee_id and not employee:
            return Response(
                {
                    "status": False,
                    "message": "Employee not found in your organization.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

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
                "is_project_head": allocation.is_project_head,
                "is_active": allocation.is_active,
            },
        )

        # ---- Notify employee of project allocation ----
        if allocation.employee.user_id:
            transaction.on_commit(lambda: notify(
                users=allocation.employee.user,
                event_code="PROJECT_TEAM_ALLOCATED",
                title="Added to a project",
                body=(
                    f"You have been added to project "
                    f"'{allocation.project.project_name}'"
                    + (
                        f" as {allocation.project_role}."
                        if allocation.project_role
                        else "."
                    )
                ),
                reference_type="project",
                reference_id=allocation.project_id,
                priority="NORMAL",
            ))

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
            "is_project_head": allocation.is_project_head,
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
            "is_project_head": allocation.is_project_head,
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
            "is_project_head": allocation.is_project_head,
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
                "is_project_head": allocation.is_project_head,
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

        head_alloc = next(
            (a for a in allocations if a.is_project_head),
            None,
        )
        project_head = None
        if head_alloc:
            emp = head_alloc.employee
            project_head = {
                "allocation_id": head_alloc.id,
                "employee_id": emp.id,
                "employee_code": emp.employee_code,
                "name": (
                    f"{emp.first_name} "
                    f"{emp.middle_name or ''} "
                    f"{emp.last_name}"
                ).replace("  ", " ").strip(),
                "project_role": head_alloc.project_role,
            }

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
                    "project_head": project_head,
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


# =========================================================
# ASSIGN PROJECT HEAD
# =========================================================
class ProjectHeadAssignAPIView(APIView):
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
            .select_for_update()
            .filter(
                id=allocation_id,
                project__organization=organization,
                project__is_active=True,
                is_active=True,
            )
            .select_related("project", "employee")
            .first()
        )

        if not allocation:
            return Response(
                {
                    "status": False,
                    "message": "Active team allocation not found for this project.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if allocation.is_project_head:
            return Response(
                {
                    "status": True,
                    "message": "This employee is already the project head.",
                    "data": ProjectTeamAllocationDetailSerializer(
                        allocation,
                        context={"request": request},
                    ).data,
                },
                status=status.HTTP_200_OK,
            )

        previous_head = (
            ProjectTeamAllocation.objects
            .select_for_update()
            .filter(
                project=allocation.project,
                is_project_head=True,
                is_active=True,
            )
            .exclude(pk=allocation.pk)
            .first()
        )

        if previous_head:
            previous_head.is_project_head = False
            previous_head.save(update_fields=["is_project_head", "updated_at"])

        allocation.is_project_head = True
        allocation.save(update_fields=["is_project_head", "updated_at"])

        log_activity(
            request=request,
            action="UPDATE",
            module="PROJECT_TEAM",
            object_type="ProjectTeamAllocation",
            object_id=allocation.id,
            description=(
                f"Project head set to '{allocation.employee.employee_code}' "
                f"for project '{allocation.project.project_name}'."
            ),
            old_data={
                "previous_head_allocation_id": (
                    previous_head.id if previous_head else None
                ),
                "previous_head_employee_id": (
                    previous_head.employee_id if previous_head else None
                ),
            },
            new_data={
                "project": allocation.project_id,
                "allocation_id": allocation.id,
                "employee_id": allocation.employee_id,
                "is_project_head": True,
            },
        )

        # ---- Notify new head ----
        if allocation.employee.user_id:
            transaction.on_commit(lambda: notify(
                users=allocation.employee.user,
                event_code="PROJECT_HEAD_ASSIGNED",
                title="You are now a project head",
                body=(
                    f"You have been assigned as the head of "
                    f"'{allocation.project.project_name}'."
                ),
                reference_type="project",
                reference_id=allocation.project_id,
                priority="HIGH",
            ))

        # ---- Notify demoted previous head ----
        if previous_head and previous_head.employee.user_id:
            transaction.on_commit(lambda: notify(
                users=previous_head.employee.user,
                event_code="PROJECT_HEAD_REVOKED",
                title="Project head role reassigned",
                body=(
                    f"You are no longer the head of "
                    f"'{previous_head.project.project_name}'. "
                    f"You remain on the team."
                ),
                reference_type="project",
                reference_id=previous_head.project_id,
                priority="NORMAL",
            ))

        return Response(
            {
                "status": True,
                "message": "Project head assigned successfully.",
                "data": ProjectTeamAllocationDetailSerializer(
                    allocation,
                    context={"request": request},
                ).data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# EMPLOYEE — MY PROJECTS
# =========================================================
class MyProjectsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        employee, error_response = get_current_employee(request)
        if error_response:
            return error_response

        allocations = (
            ProjectTeamAllocation.objects
            .filter(
                employee=employee,
                is_active=True,
                project__is_active=True,
            )
            .select_related("project", "project__client")
            .order_by("-created_at")
        )

        serializer = ProjectTeamEmployeeSerializer(
            allocations,
            many=True,
            context={"request": request},
        )

        return Response(
            {
                "status": True,
                "message": "My projects fetched successfully.",
                "data": {
                    "project_count": allocations.count(),
                    "projects": serializer.data,
                },
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# EMPLOYEE — MY PROJECTS AS HEAD
# =========================================================
class MyProjectsAsHeadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        employee, error_response = get_current_employee(request)
        if error_response:
            return error_response

        allocations = (
            ProjectTeamAllocation.objects
            .filter(
                employee=employee,
                is_active=True,
                is_project_head=True,
                project__is_active=True,
            )
            .select_related("project", "project__client")
            .order_by("-created_at")
        )

        serializer = ProjectTeamEmployeeSerializer(
            allocations,
            many=True,
            context={"request": request},
        )

        return Response(
            {
                "status": True,
                "message": "Projects headed by you fetched successfully.",
                "data": {
                    "project_count": allocations.count(),
                    "projects": serializer.data,
                },
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# EMPLOYEE — MY PROJECT DETAIL
# =========================================================
class MyProjectDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        employee, error_response = get_current_employee(request)
        if error_response:
            return error_response

        project_id = request.data.get("project_id")
        if not project_id:
            return Response(
                {"status": False, "message": "project_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Must be allocated to this project.
        allocated = ProjectTeamAllocation.objects.filter(
            project_id=project_id,
            employee=employee,
            is_active=True,
            project__is_active=True,
        ).exists()

        if not allocated:
            return Response(
                {
                    "status": False,
                    "message": "Project not found or you are not allocated to it.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        project = (
            Project.objects
            .filter(id=project_id, is_active=True)
            .select_related("client")
            .prefetch_related("documents", "team_allocations__employee")
            .first()
        )

        serializer = MyProjectDetailSerializer(
            project,
            context={"request": request},
        )

        return Response(
            {
                "status": True,
                "message": "Project detail fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# TASK — CREATE
# =========================================================
class TaskCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        project_id = request.data.get("project")
        permission, project, _allocation, err = get_project_permission(
            request, project_id
        )
        if err:
            return err

        if permission not in ("ADMIN", "HEAD"):
            return Response(
                {
                    "status": False,
                    "message": "Only the project head or organization admin can create tasks.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if project.organization_id != organization.id:
            return Response(
                {
                    "status": False,
                    "message": "Project not found in your organization.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = TaskCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        task = serializer.save(
            organization=project.organization,
            status="TODO",
            created_by=request.user,
            updated_by=request.user,
        )

        log_activity(
            request=request,
            action="CREATE",
            module="TASK",
            object_type="Task",
            object_id=task.id,
            description=f"Task '{task.title}' created in project '{project.project_name}'.",
            new_data={
                "project": task.project_id,
                "organization_id": task.organization_id,
                "title": task.title,
                "description": task.description,
                "priority": task.priority,
                "assigned_to": task.assigned_to_id,
                "due_date": task.due_date,
                "estimated_hours": (
                    str(task.estimated_hours)
                    if task.estimated_hours is not None
                    else None
                ),
                "status": task.status,
            },
        )

        # ---- Notify assignee of new task ----
        if task.assigned_to_id and task.assigned_to.user_id:
            transaction.on_commit(lambda: notify(
                users=task.assigned_to.user,
                event_code="TASK_ASSIGNED",
                title="New task assigned",
                body=(
                    f"You have been assigned '{task.title}' "
                    f"in '{task.project.project_name}'"
                    + (
                        f" (due {task.due_date})."
                        if task.due_date
                        else "."
                    )
                ),
                reference_type="task",
                reference_id=task.id,
                priority="HIGH",
            ))

        return Response(
            {
                "status": True,
                "message": "Task created successfully.",
                "data": TaskDetailSerializer(
                    task, context={"request": request}
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


# =========================================================
# TASK — LIST (supports {} for all accessible projects)
# =========================================================
class TaskListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        project_id = request.data.get("project_id")

        # ---- Single-project mode (existing behaviour) ----
        if project_id:
            permission, project, _allocation, err = get_project_permission(
                request, project_id
            )
            if err:
                return err

            if permission not in ("ADMIN", "HEAD"):
                return Response(
                    {
                        "status": False,
                        "message": (
                            "Only the project head or organization admin "
                            "can view the task list."
                        ),
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            tasks = Task.objects.filter(
                project=project,
                is_active=True,
            )

        # ---- Cross-project mode ({}) ----
        else:
            projects, permission_map, err = get_accessible_projects(request)
            if err:
                return err

            # Only ADMIN/HEAD projects contribute to the cross-project list.
            # (MEMBERS should use /task/my-tasks/ for their own tasks.)
            allowed_project_ids = [
                pid for pid, perm in permission_map.items()
                if perm in ("ADMIN", "HEAD")
            ]
            if not allowed_project_ids:
                return Response(
                    {
                        "status": False,
                        "message": (
                            "You do not have access to any project "
                            "task list."
                        ),
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            tasks = Task.objects.filter(
                project_id__in=allowed_project_ids,
                is_active=True,
            )

        # ---- Common filtering / select_related ----
        tasks = tasks.select_related(
            "project", "project__client", "assigned_to"
        )

        task_status = request.data.get("status")
        priority = request.data.get("priority")
        assigned_to_id = request.data.get("assigned_to_id")
        search = request.data.get("search")

        if task_status:
            tasks = tasks.filter(status=task_status)

        if priority:
            tasks = tasks.filter(priority=priority)

        if assigned_to_id:
            tasks = tasks.filter(assigned_to_id=assigned_to_id)

        if search:
            search = search.strip()
            tasks = tasks.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
            )

        tasks = tasks.order_by("-created_at")

        serializer = TaskListSerializer(
            tasks, many=True, context={"request": request}
        )

        return Response(
            {
                "status": True,
                "message": "Tasks fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# TASK — DETAIL
# =========================================================
class TaskDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        task_id = request.data.get("task_id")
        if not task_id:
            return Response(
                {"status": False, "message": "task_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task = (
            Task.objects
            .filter(id=task_id, is_active=True)
            .select_related(
                "project",
                "project__client",
                "assigned_to",
                "created_by",
                "updated_by",
            )
            .first()
        )

        if not task:
            return Response(
                {"status": False, "message": "Task not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        permission, _project, _allocation, err = get_project_permission(
            request, task.project_id
        )
        if err:
            return err

        # Members can view task only if it's assigned to them.
        if permission == "MEMBER":
            employee = getattr(request.user, "employee_profile", None)
            if not employee or task.assigned_to_id != employee.id:
                return Response(
                    {
                        "status": False,
                        "message": "You do not have access to this task.",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        if permission is None:
            return Response(
                {
                    "status": False,
                    "message": "You do not have access to this task.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = TaskDetailSerializer(
            task, context={"request": request}
        )

        return Response(
            {
                "status": True,
                "message": "Task detail fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# TASK — UPDATE (fields, head/admin only)
# =========================================================
class TaskUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        task_id = request.data.get("task_id")
        if not task_id:
            return Response(
                {"status": False, "message": "task_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task = (
            Task.objects
            .filter(id=task_id, is_active=True)
            .select_related("project", "assigned_to")
            .first()
        )

        if not task:
            return Response(
                {"status": False, "message": "Task not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        permission, _project, _allocation, err = get_project_permission(
            request, task.project_id
        )
        if err:
            return err

        if permission not in ("ADMIN", "HEAD"):
            return Response(
                {
                    "status": False,
                    "message": "Only the project head or organization admin can update tasks.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        old_data = {
            "title": task.title,
            "description": task.description,
            "priority": task.priority,
            "assigned_to": task.assigned_to_id,
            "due_date": task.due_date,
            "estimated_hours": (
                str(task.estimated_hours)
                if task.estimated_hours is not None
                else None
            ),
            "actual_hours": (
                str(task.actual_hours)
                if task.actual_hours is not None
                else None
            ),
        }

        data = request.data.copy()
        data.pop("task_id", None)

        serializer = TaskUpdateSerializer(
            task, data=data, partial=True
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

        task = serializer.save(updated_by=request.user)

        new_data = {
            "title": task.title,
            "description": task.description,
            "priority": task.priority,
            "assigned_to": task.assigned_to_id,
            "due_date": task.due_date,
            "estimated_hours": (
                str(task.estimated_hours)
                if task.estimated_hours is not None
                else None
            ),
            "actual_hours": (
                str(task.actual_hours)
                if task.actual_hours is not None
                else None
            ),
        }

        log_activity(
            request=request,
            action="UPDATE",
            module="TASK",
            object_type="Task",
            object_id=task.id,
            description=f"Task '{task.title}' updated.",
            old_data=old_data,
            new_data=new_data,
        )

        # ---- Notify new assignee if reassigned ----
        old_assignee_id = old_data.get("assigned_to")
        new_assignee_id = task.assigned_to_id

        if (
            new_assignee_id
            and new_assignee_id != old_assignee_id
            and task.assigned_to
            and task.assigned_to.user_id
        ):
            transaction.on_commit(lambda: notify(
                users=task.assigned_to.user,
                event_code="TASK_REASSIGNED",
                title="Task assigned to you",
                body=(
                    f"'{task.title}' in '{task.project.project_name}' "
                    f"has been assigned to you."
                ),
                reference_type="task",
                reference_id=task.id,
                priority="HIGH",
            ))

        return Response(
            {
                "status": True,
                "message": "Task updated successfully.",
                "data": TaskDetailSerializer(
                    task, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# TASK — STATUS UPDATE (permission matrix)
# =========================================================
class TaskStatusUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    # Assignee-allowed transitions
    ASSIGNEE_TRANSITIONS = {
        ("TODO", "IN_PROGRESS"),
        ("IN_PROGRESS", "TODO"),
        ("IN_PROGRESS", "IN_REVIEW"),
    }

    # Head/admin transitions (any of these)
    HEAD_TRANSITIONS = {
        ("TODO", "IN_PROGRESS"),
        ("TODO", "IN_REVIEW"),
        ("IN_PROGRESS", "TODO"),
        ("IN_PROGRESS", "IN_REVIEW"),
        ("IN_REVIEW", "DONE"),
        ("IN_REVIEW", "IN_PROGRESS"),
        ("DONE", "IN_PROGRESS"),
        ("DONE", "TODO"),
    }

    @transaction.atomic
    def post(self, request):
        task_id = request.data.get("task_id")
        if not task_id:
            return Response(
                {"status": False, "message": "task_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task = (
            Task.objects
            .filter(id=task_id, is_active=True)
            .select_related("project", "assigned_to")
            .first()
        )

        if not task:
            return Response(
                {"status": False, "message": "Task not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        organization, error_response = get_user_organization(request)
        if error_response:
            return error_response

        permission, _project, _allocation, err = get_project_permission(
            request, task.project_id
        )
        if err:
            return err

        serializer = TaskStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_status = serializer.validated_data["status"]
        actual_hours = serializer.validated_data.get("actual_hours", None)

        old_status = task.status
        transition = (old_status, new_status)

        # Determine caller role for this task
        employee = getattr(request.user, "employee_profile", None)
        is_assignee = bool(
            employee and task.assigned_to_id == employee.id
        )

        if permission in ("ADMIN", "HEAD"):
            allowed = self.HEAD_TRANSITIONS
        elif permission == "MEMBER" and is_assignee:
            allowed = self.ASSIGNEE_TRANSITIONS
        else:
            return Response(
                {
                    "status": False,
                    "message": "You are not allowed to change the status of this task.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if old_status == new_status:
            # No-op; treat as success
            return Response(
                {
                    "status": True,
                    "message": "Task status unchanged.",
                    "data": TaskDetailSerializer(
                        task, context={"request": request}
                    ).data,
                },
                status=status.HTTP_200_OK,
            )

        if transition not in allowed:
            return Response(
                {
                    "status": False,
                    "message": (
                        f"Transition from '{old_status}' to '{new_status}' "
                        f"is not allowed for your role."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        task.status = new_status
        if actual_hours is not None:
            task.actual_hours = actual_hours

        if new_status == "DONE":
            task.completed_at = timezone.now()
        elif old_status == "DONE" and new_status != "DONE":
            task.completed_at = None

        task.updated_by = request.user
        task.save(
            update_fields=[
                "status",
                "actual_hours",
                "completed_at",
                "updated_by",
                "updated_at",
            ]
        )

        log_activity(
            request=request,
            action="UPDATE",
            module="TASK",
            object_type="Task",
            object_id=task.id,
            description=(
                f"Task '{task.title}' status changed "
                f"from '{old_status}' to '{new_status}'."
            ),
            old_data={
                "status": old_status,
                "actual_hours": (
                    str(task.actual_hours)
                    if task.actual_hours is not None
                    else None
                ),
            },
            new_data={
                "status": new_status,
                "actual_hours": (
                    str(task.actual_hours)
                    if task.actual_hours is not None
                    else None
                ),
                "completed_at": (
                    task.completed_at.isoformat()
                    if task.completed_at
                    else None
                ),
            },
        )

        # ---- Notify on specific status transitions ----
        if new_status == "IN_REVIEW":
            # Assignee submitted for review → notify head + admin
            if task.assigned_to and task.assigned_to.user_id:
                recipients = _get_project_notification_recipients(
                    task.project, organization
                )
                # Remove the assignee themselves (don't notify the person who did the action)
                recipients = [
                    u for u in recipients if u.id != task.assigned_to.user_id
                ]
                if recipients:
                    transaction.on_commit(lambda: notify(
                        users=recipients,
                        event_code="TASK_IN_REVIEW",
                        title="Task ready for review",
                        body=(
                            f"'{task.title}' in "
                            f"'{task.project.project_name}' is ready for review."
                        ),
                        reference_type="task",
                        reference_id=task.id,
                        priority="NORMAL",
                    ))

        elif new_status == "DONE" and old_status != "DONE":
            # Head/admin marked task DONE → notify assignee
            if task.assigned_to and task.assigned_to.user_id:
                transaction.on_commit(lambda: notify(
                    users=task.assigned_to.user,
                    event_code="TASK_COMPLETED",
                    title="Task completed",
                    body=(
                        f"'{task.title}' in "
                        f"'{task.project.project_name}' has been marked as done."
                    ),
                    reference_type="task",
                    reference_id=task.id,
                    priority="NORMAL",
                ))

        elif (
            old_status == "DONE" and new_status != "DONE"
        ) or (
            old_status == "IN_REVIEW" and new_status == "IN_PROGRESS"
        ):
            # Head/admin reopened a task → notify assignee
            if task.assigned_to and task.assigned_to.user_id:
                transaction.on_commit(lambda: notify(
                    users=task.assigned_to.user,
                    event_code="TASK_REOPENED",
                    title="Task reopened",
                    body=(
                        f"'{task.title}' in "
                        f"'{task.project.project_name}' has been reopened. "
                        f"Please address the feedback."
                    ),
                    reference_type="task",
                    reference_id=task.id,
                    priority="HIGH",
                ))

        return Response(
            {
                "status": True,
                "message": "Task status updated successfully.",
                "data": TaskDetailSerializer(
                    task, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# TASK — DEACTIVATE
# =========================================================
class TaskDeactivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        task_id = request.data.get("task_id")
        if not task_id:
            return Response(
                {"status": False, "message": "task_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task = (
            Task.objects
            .filter(id=task_id, is_active=True)
            .select_related("project")
            .first()
        )

        if not task:
            return Response(
                {"status": False, "message": "Task not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        permission, _project, _allocation, err = get_project_permission(
            request, task.project_id
        )
        if err:
            return err

        if permission not in ("ADMIN", "HEAD"):
            return Response(
                {
                    "status": False,
                    "message": "Only the project head or organization admin can deactivate tasks.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        old_data = {"is_active": task.is_active}

        task.is_active = False
        task.updated_by = request.user
        task.save(update_fields=["is_active", "updated_by", "updated_at"])

        log_activity(
            request=request,
            action="DELETE",
            module="TASK",
            object_type="Task",
            object_id=task.id,
            description=f"Task '{task.title}' deactivated.",
            old_data=old_data,
            new_data={"is_active": False},
        )

        return Response(
            {
                "status": True,
                "message": "Task deactivated successfully.",
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# EMPLOYEE — MY TASKS
# =========================================================
class MyTasksAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        employee, error_response = get_current_employee(request)
        if error_response:
            return error_response

        tasks = (
            Task.objects
            .filter(
                assigned_to=employee,
                is_active=True,
                project__is_active=True,
            )
            .select_related("project", "project__client")
            .order_by("-created_at")
        )

        task_status = request.data.get("status")
        priority = request.data.get("priority")
        project_id = request.data.get("project_id")
        search = request.data.get("search")

        if task_status:
            tasks = tasks.filter(status=task_status)

        if priority:
            tasks = tasks.filter(priority=priority)

        if project_id:
            tasks = tasks.filter(project_id=project_id)

        if search:
            search = search.strip()
            tasks = tasks.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
            )

        serializer = TaskEmployeeSerializer(
            tasks, many=True, context={"request": request}
        )

        return Response(
            {
                "status": True,
                "message": "My tasks fetched successfully.",
                "data": {
                    "task_count": tasks.count(),
                    "tasks": serializer.data,
                },
            },
            status=status.HTTP_200_OK,
        )
