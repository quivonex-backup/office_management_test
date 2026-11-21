from rest_framework import serializers
from .models import Project, ProjectDocument, ProjectTeamAllocation, Task
from app.employees.models import Employee


# =========================================================
# PROJECT DOCUMENT SERIALIZER
# =========================================================
class ProjectDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectDocument
        fields = ["id", "title", "file", "description", "created_at"]
        read_only_fields = ["id", "created_at"]


# =========================================================
# PROJECT CREATE SERIALIZER
# =========================================================
class ProjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "project_name",
            "client",
            "project_type",
            "description",
            "start_date",
            "end_date",
            "deadline",
            "priority",
            "status",
            "total_cost",
            "live_url",
        ]

    def validate_total_cost(self, value):
        if value < 0:
            raise serializers.ValidationError("Total cost cannot be negative.")
        return value

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        deadline = attrs.get("deadline")

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                "end_date": "End date cannot be before start date."
            })

        if start_date and deadline and deadline < start_date:
            raise serializers.ValidationError({
                "deadline": "Deadline cannot be before start date."
            })

        return attrs


# =========================================================
# PROJECT LIST SERIALIZER
# =========================================================
class ProjectListSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.client_name", read_only=True)
    documents = ProjectDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "project_name",
            "client",
            "client_name",
            "project_type",
            "start_date",
            "end_date",
            "deadline",
            "priority",
            "status",
            "total_cost",
            "live_url",
            "documents",
            "is_active",
            "created_at",
        ]


# =========================================================
# PROJECT DETAIL SERIALIZER
# =========================================================
class ProjectDetailSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.client_name", read_only=True)
    documents = ProjectDocumentSerializer(many=True, read_only=True)
    project_head = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "project_name",
            "client",
            "client_name",
            "project_type",
            "description",
            "start_date",
            "end_date",
            "deadline",
            "priority",
            "status",
            "total_cost",
            "live_url",
            "documents",
            "project_head",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_project_head(self, obj):
        # obj.team_allocations is prefetched in the detail view
        for alloc in obj.team_allocations.all():
            if alloc.is_project_head and alloc.is_active:
                emp = alloc.employee
                name = (
                    f"{emp.first_name} "
                    f"{emp.middle_name or ''} "
                    f"{emp.last_name}"
                ).replace("  ", " ").strip()
                return {
                    "allocation_id": alloc.id,
                    "employee_id": emp.id,
                    "employee_code": emp.employee_code,
                    "name": name,
                    "project_role": alloc.project_role,
                }
        return None


# =========================================================
# PROJECT UPDATE SERIALIZER
# =========================================================
class ProjectUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "project_name",
            "client",
            "project_type",
            "description",
            "start_date",
            "end_date",
            "deadline",
            "priority",
            "status",
            "total_cost",
            "live_url",
        ]
        extra_kwargs = {
            "project_name": {"required": False},
            "client": {"required": False},
        }

    def validate_total_cost(self, value):
        if value < 0:
            raise serializers.ValidationError("Total cost cannot be negative.")
        return value

    def validate(self, attrs):
        start_date = attrs.get(
            "start_date",
            self.instance.start_date if self.instance else None
        )
        end_date = attrs.get(
            "end_date",
            self.instance.end_date if self.instance else None
        )
        deadline = attrs.get(
            "deadline",
            self.instance.deadline if self.instance else None
        )

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                "end_date": "End date cannot be before start date."
            })

        if start_date and deadline and deadline < start_date:
            raise serializers.ValidationError({
                "deadline": "Deadline cannot be before start date."
            })

        return attrs


# =========================================================
# PROJECT TEAM ALLOCATION SERIALIZER
# =========================================================
class ProjectTeamAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectTeamAllocation
        fields = [
            "id",
            "project",
            "employee",
            "project_role",
            "allocation_percentage",
            "start_date",
            "end_date",
            "notes",
            "is_active",
            "allocated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "allocated_by",
            "created_at",
            "updated_at",
        ]

    def validate_project(self, project):
        if not project.is_active:
            raise serializers.ValidationError(
                "Selected project is inactive."
            )
        return project

    def validate_employee(self, employee):
        if not employee.is_active:
            raise serializers.ValidationError(
                "Selected employee is inactive."
            )
        if employee.employment_status != "ACTIVE":
            raise serializers.ValidationError(
                "Selected employee is not currently active."
            )
        return employee

    def validate_allocation_percentage(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Allocation percentage must be greater than 0."
            )
        if value > 100:
            raise serializers.ValidationError(
                "Allocation percentage cannot exceed 100."
            )
        return value

    def validate(self, attrs):
        project = attrs.get(
            "project",
            getattr(self.instance, "project", None)
        )
        employee = attrs.get(
            "employee",
            getattr(self.instance, "employee", None)
        )
        start_date = attrs.get(
            "start_date",
            getattr(self.instance, "start_date", None)
        )
        end_date = attrs.get(
            "end_date",
            getattr(self.instance, "end_date", None)
        )
        is_active = attrs.get(
            "is_active",
            getattr(self.instance, "is_active", True)
        )

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                "end_date": "End date cannot be before start date."
            })

        # NEW: cross-organization safety
        if project and employee:
            if project.organization_id != employee.organization_id:
                raise serializers.ValidationError(
                    "Project and employee must belong to the same organization."
                )

        if project and employee and is_active:
            queryset = ProjectTeamAllocation.objects.filter(
                project=project,
                employee=employee,
                is_active=True,
            )
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    "This employee is already actively allocated "
                    "to this project."
                )

        return attrs


# =========================================================
# PROJECT TEAM ALLOCATION LIST SERIALIZER
# =========================================================
class ProjectTeamAllocationListSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.project_name", read_only=True)
    project_id = serializers.IntegerField(source="project.id", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)
    employee_name = serializers.SerializerMethodField()
    employee_designation = serializers.CharField(source="employee.designation", read_only=True)

    class Meta:
        model = ProjectTeamAllocation
        fields = [
            "id",
            "project_id",
            "project_name",
            "employee_code",
            "employee_name",
            "employee_designation",
            "project_role",
            "allocation_percentage",
            "start_date",
            "end_date",
            "is_project_head",
            "is_active",
            "notes",
            "created_at",
            "updated_at",
        ]

    def get_employee_name(self, obj):
        return (
            f"{obj.employee.first_name} "
            f"{obj.employee.middle_name or ''} "
            f"{obj.employee.last_name}"
        ).replace("  ", " ").strip()


# =========================================================
# PROJECT TEAM ALLOCATION DETAIL SERIALIZER
# =========================================================

class ProjectTeamAllocationDetailSerializer(serializers.ModelSerializer):
    project_details = serializers.SerializerMethodField()
    employee_details = serializers.SerializerMethodField()
    allocated_by_details = serializers.SerializerMethodField()

    class Meta:
        model = ProjectTeamAllocation
        fields = [
            "id",
            "project_details",
            "employee_details",
            "project_role",
            "allocation_percentage",
            "start_date",
            "end_date",
            "notes",
            "is_project_head",
            "is_active",
            "allocated_by_details",
            "created_at",
            "updated_at",
        ]

    def get_project_details(self, obj):
        return {
            "id": obj.project.id,
            "project_name": obj.project.project_name,
            "project_type": obj.project.project_type,
            "status": obj.project.status,
            "priority": obj.project.priority,
            "client_id": obj.project.client.id,
            "client_name": obj.project.client.client_name,
        }

    def get_employee_details(self, obj):
        employee = obj.employee
        employee_name = (
            f"{employee.first_name} "
            f"{employee.middle_name or ''} "
            f"{employee.last_name}"
        ).replace("  ", " ").strip()
        return {
            "id": employee.id,
            "employee_code": employee.employee_code,
            "name": employee_name,
            "designation": employee.designation,
            "department": employee.department,
            "employment_status": employee.employment_status,
            "mobile": employee.mobile,
            "email": employee.personal_email,
        }

    def get_allocated_by_details(self, obj):
        if not obj.allocated_by:
            return None
        return {
            "id": obj.allocated_by.id,
            "username": obj.allocated_by.username,
            "email": obj.allocated_by.email,
        }


# =========================================================
# PROJECT TEAM SERIALIZER
# =========================================================

class ProjectTeamProjectSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)

    class Meta:
        model = ProjectTeamAllocation
        fields = [
            "id",
            "employee_code",
            "employee_name",
            "project_role",
            "allocation_percentage",
            "start_date",
            "end_date",
            "is_project_head",
            "is_active",
            "notes",
        ]

    def get_employee_name(self, obj):
        employee = obj.employee
        return (
            f"{employee.first_name} "
            f"{employee.middle_name or ''} "
            f"{employee.last_name}"
        ).replace("  ", " ").strip()


# =========================================================
# EMPLOYEE PROJECTS SERIALIZER
# =========================================================
class ProjectTeamEmployeeSerializer(serializers.ModelSerializer):
    project_id = serializers.IntegerField(source="project.id", read_only=True)
    project_name = serializers.CharField(source="project.project_name", read_only=True)
    project_status = serializers.CharField(source="project.status", read_only=True)
    project_priority = serializers.CharField(source="project.priority", read_only=True)
    client_name = serializers.CharField(source="project.client.client_name", read_only=True)

    class Meta:
        model = ProjectTeamAllocation
        fields = [
            "id",
            "project_id",
            "project_name",
            "project_status",
            "project_priority",
            "client_name",
            "project_role",
            "allocation_percentage",
            "start_date",
            "end_date",
            "is_project_head",
            "is_active",
            "notes",
        ]


# =========================================================
# TASK — SHARED HELPERS
# =========================================================
def _employee_display_name(employee):
    if not employee:
        return None
    return (
        f"{employee.first_name} "
        f"{employee.middle_name or ''} "
        f"{employee.last_name}"
    ).replace("  ", " ").strip()


# =========================================================
# TASK CREATE SERIALIZER
# =========================================================
class TaskCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Task
        fields = [
            "project",
            "title",
            "description",
            "priority",
            "assigned_to",
            "due_date",
            "estimated_hours",
        ]

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Title cannot be blank.")
        return value

    def validate_estimated_hours(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Estimated hours cannot be negative."
            )
        return value

    def validate(self, attrs):
        project = attrs.get("project")
        assigned_to = attrs.get("assigned_to")

        if project and not project.is_active:
            raise serializers.ValidationError(
                {"project": "Selected project is inactive."}
            )

        # Cross-organization safety
        if project and assigned_to:
            if assigned_to.organization_id != project.organization_id:
                raise serializers.ValidationError(
                    "Assignee must belong to the same organization as the project."
                )

        if assigned_to:
            if not assigned_to.is_active:
                raise serializers.ValidationError(
                    {"assigned_to": "Selected employee is inactive."}
                )
            if assigned_to.employment_status != "ACTIVE":
                raise serializers.ValidationError(
                    {"assigned_to": "Selected employee is not currently active."}
                )

        # Assignee must be allocated to this project
        if project and assigned_to:
            allocated = ProjectTeamAllocation.objects.filter(
                project=project,
                employee=assigned_to,
                is_active=True,
            ).exists()
            if not allocated:
                raise serializers.ValidationError(
                    {"assigned_to": "Selected employee is not allocated to this project."}
                )

        return attrs


# =========================================================
# TASK UPDATE SERIALIZER
# =========================================================
class TaskUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Task
        fields = [
            "title",
            "description",
            "priority",
            "assigned_to",
            "due_date",
            "estimated_hours",
            "actual_hours",
        ]
        extra_kwargs = {
            "title": {"required": False},
        }

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Title cannot be blank.")
        return value

    def validate_estimated_hours(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Estimated hours cannot be negative."
            )
        return value

    def validate_actual_hours(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Actual hours cannot be negative."
            )
        return value

    def validate(self, attrs):
        task = self.instance
        assigned_to = attrs.get("assigned_to", task.assigned_to if task else None)

        if task and assigned_to:
            if assigned_to.organization_id != task.organization_id:
                raise serializers.ValidationError(
                    "Assignee must belong to the same organization as the project."
                )
            if not assigned_to.is_active:
                raise serializers.ValidationError(
                    {"assigned_to": "Selected employee is inactive."}
                )
            if assigned_to.employment_status != "ACTIVE":
                raise serializers.ValidationError(
                    {"assigned_to": "Selected employee is not currently active."}
                )
            allocated = ProjectTeamAllocation.objects.filter(
                project=task.project,
                employee=assigned_to,
                is_active=True,
            ).exists()
            if not allocated:
                raise serializers.ValidationError(
                    {"assigned_to": "Selected employee is not allocated to this project."}
                )

        return attrs


# =========================================================
# TASK STATUS UPDATE SERIALIZER
# =========================================================
class TaskStatusUpdateSerializer(serializers.Serializer):

    status = serializers.ChoiceField(choices=Task.STATUS_CHOICES)
    actual_hours = serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        required=False,
        allow_null=True,
    )

    def validate_actual_hours(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Actual hours cannot be negative."
            )
        return value


# =========================================================
# TASK LIST SERIALIZER
# =========================================================
class TaskListSerializer(serializers.ModelSerializer):

    project_id = serializers.IntegerField(source="project.id", read_only=True)
    project_name = serializers.CharField(
        source="project.project_name", read_only=True
    )
    assigned_to_details = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "project_id",
            "project_name",
            "title",
            "status",
            "priority",
            "assigned_to_details",
            "due_date",
            "estimated_hours",
            "actual_hours",
            "completed_at",
            "created_at",
        ]

    def get_assigned_to_details(self, obj):
        emp = obj.assigned_to
        if not emp:
            return None
        return {
            "id": emp.id,
            "employee_code": emp.employee_code,
            "name": _employee_display_name(emp),
            "designation": emp.designation,
        }


# =========================================================
# TASK DETAIL SERIALIZER
# =========================================================
class TaskDetailSerializer(serializers.ModelSerializer):

    project_details = serializers.SerializerMethodField()
    assigned_to_details = serializers.SerializerMethodField()
    created_by_details = serializers.SerializerMethodField()
    updated_by_details = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "project_details",
            "title",
            "description",
            "status",
            "priority",
            "assigned_to_details",
            "due_date",
            "estimated_hours",
            "actual_hours",
            "completed_at",
            "is_active",
            "created_by_details",
            "updated_by_details",
            "created_at",
            "updated_at",
        ]

    def get_project_details(self, obj):
        return {
            "id": obj.project.id,
            "project_name": obj.project.project_name,
            "project_code": obj.project.project_code,
            "client_id": obj.project.client_id,
            "client_name": obj.project.client.client_name,
            "status": obj.project.status,
            "priority": obj.project.priority,
        }

    def get_assigned_to_details(self, obj):
        emp = obj.assigned_to
        if not emp:
            return None
        return {
            "id": emp.id,
            "employee_code": emp.employee_code,
            "name": _employee_display_name(emp),
            "designation": emp.designation,
            "department": emp.department,
        }

    def get_created_by_details(self, obj):
        if not obj.created_by:
            return None
        return {
            "id": obj.created_by.id,
            "username": obj.created_by.username,
            "email": obj.created_by.email,
        }

    def get_updated_by_details(self, obj):
        if not obj.updated_by:
            return None
        return {
            "id": obj.updated_by.id,
            "username": obj.updated_by.username,
            "email": obj.updated_by.email,
        }


# =========================================================
# TASK EMPLOYEE SERIALIZER (for /task/my-tasks/)
# =========================================================
class TaskEmployeeSerializer(serializers.ModelSerializer):

    project_id = serializers.IntegerField(source="project.id", read_only=True)
    project_name = serializers.CharField(
        source="project.project_name", read_only=True
    )
    project_code = serializers.CharField(
        source="project.project_code", read_only=True
    )

    class Meta:
        model = Task
        fields = [
            "id",
            "project_id",
            "project_name",
            "project_code",
            "title",
            "description",
            "status",
            "priority",
            "due_date",
            "estimated_hours",
            "actual_hours",
            "completed_at",
            "created_at",
            "updated_at",
        ]


# =========================================================
# MY PROJECT DETAIL SERIALIZER (for /project/my-project-detail/)
# =========================================================
class MyProjectDetailSerializer(serializers.ModelSerializer):

    client_name = serializers.CharField(
        source="client.client_name", read_only=True
    )
    documents = ProjectDocumentSerializer(many=True, read_only=True)
    project_head = serializers.SerializerMethodField()
    team = serializers.SerializerMethodField()
    my_role = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "project_code",
            "project_name",
            "client",
            "client_name",
            "project_type",
            "description",
            "start_date",
            "end_date",
            "deadline",
            "priority",
            "status",
            "live_url",
            "documents",
            "project_head",
            "team",
            "my_role",
            "created_at",
            "updated_at",
        ]

    def _active_allocations(self, obj):
        # Prefetched in view. Return list so we can reuse.
        return [a for a in obj.team_allocations.all() if a.is_active]

    def get_project_head(self, obj):
        for alloc in self._active_allocations(obj):
            if alloc.is_project_head:
                emp = alloc.employee
                return {
                    "allocation_id": alloc.id,
                    "employee_id": emp.id,
                    "employee_code": emp.employee_code,
                    "name": _employee_display_name(emp),
                    "project_role": alloc.project_role,
                }
        return None

    def get_team(self, obj):
        data = []
        for alloc in self._active_allocations(obj):
            emp = alloc.employee
            data.append({
                "allocation_id": alloc.id,
                "employee_id": emp.id,
                "employee_code": emp.employee_code,
                "name": _employee_display_name(emp),
                "designation": emp.designation,
                "project_role": alloc.project_role,
                "allocation_percentage": str(alloc.allocation_percentage),
                "is_project_head": alloc.is_project_head,
                "start_date": alloc.start_date,
                "end_date": alloc.end_date,
            })
        return data

    def get_my_role(self, obj):
        request = self.context.get("request")
        if not request:
            return None
        employee = getattr(request.user, "employee_profile", None)
        if not employee:
            return None
        for alloc in self._active_allocations(obj):
            if alloc.employee_id == employee.id:
                return {
                    "allocation_id": alloc.id,
                    "is_project_head": alloc.is_project_head,
                    "project_role": alloc.project_role,
                    "allocation_percentage": str(alloc.allocation_percentage),
                    "start_date": alloc.start_date,
                    "end_date": alloc.end_date,
                }
        return None
