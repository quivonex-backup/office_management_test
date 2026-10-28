from rest_framework import serializers
from .models import Project, ProjectDocument, ProjectTeamAllocation
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
            "is_active",
            "created_at",
            "updated_at",
        ]


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
        if start_date and end_date:
            if end_date < start_date:
                raise serializers.ValidationError({
                    "end_date": "End date cannot be before start date."
                })
        if project and employee and is_active:
            queryset = ProjectTeamAllocation.objects.filter(
                project=project,
                employee=employee,
                is_active=True
            )
            if self.instance:
                queryset = queryset.exclude(
                    pk=self.instance.pk
                )
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
    project_name = serializers.CharField(source="project.project_name", read_only=True)
    project_status = serializers.CharField(source="project.status", read_only=True)
    project_priority = serializers.CharField(source="project.priority", read_only=True)
    client_name = serializers.CharField(source="project.client.client_name", read_only=True)

    class Meta:
        model = ProjectTeamAllocation
        fields = [
            "id",
            "project_name",
            "project_status",
            "project_priority",
            "client_name",
            "project_role",
            "allocation_percentage",
            "start_date",
            "end_date",
            "is_active",
            "notes",
        ]