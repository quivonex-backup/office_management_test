from rest_framework import serializers
from .models import Department, Designation, Employee, EmployeeDocument


# =========================================================
# EMPLOYEE DOCUMENT SERIALIZER
# =========================================================
class EmployeeDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeDocument
        fields = [
            'id',
            'title',
            'file',
            'description',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
        ]



# =========================================================
# BATCH 1: ORGANIZATION LINKS IN EMPLOYEE RESPONSES
# =========================================================
def _ref(obj):
    return {"id": obj.id, "name": obj.name} if obj else None


class EmployeeOrgLinksMixin(serializers.Serializer):
    branch = serializers.SerializerMethodField()
    department_ref = serializers.SerializerMethodField()
    designation_ref = serializers.SerializerMethodField()
    access_role = serializers.SerializerMethodField()
    reports_to = serializers.SerializerMethodField()

    ORG_LINK_FIELDS = ["branch", "department_ref", "designation_ref", "access_role", "reports_to"]

    def get_branch(self, obj):
        return _ref(obj.branch)

    def get_department_ref(self, obj):
        return _ref(obj.department_ref)

    def get_designation_ref(self, obj):
        return _ref(obj.designation_ref)

    def get_access_role(self, obj):
        return _ref(obj.access_role)

    def get_reports_to(self, obj):
        m = obj.reports_to
        if not m:
            return None
        return {"id": m.id, "employee_code": m.employee_code,
                "full_name": " ".join(p for p in [m.first_name, m.middle_name, m.last_name] if p)}


class _OrgUniqueNameMixin:
    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Name is required.")
        qs = self.Meta.model.objects.filter(organization=self.context["organization"], name__iexact=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This name already exists in your organization.")
        return value


class DepartmentSerializer(serializers.ModelSerializer):
    employee_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Department
        fields = ["id", "name", "code", "is_active", "employee_count", "created_at", "updated_at"]


class DepartmentWriteSerializer(_OrgUniqueNameMixin, serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["name", "code"]


class DesignationSerializer(serializers.ModelSerializer):
    employee_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Designation
        fields = ["id", "name", "is_active", "employee_count", "created_at", "updated_at"]


class DesignationWriteSerializer(_OrgUniqueNameMixin, serializers.ModelSerializer):
    class Meta:
        model = Designation
        fields = ["name"]


# =========================================================
# EMPLOYEE CREATE SERIALIZER
# =========================================================
class EmployeeCreateSerializer(serializers.ModelSerializer):
    create_user = serializers.BooleanField(
        required=False,
        default=False,
        write_only=True,
    )

    class Meta:
        model = Employee
        fields = [
            "first_name",
            "middle_name",
            "last_name",
            "date_of_birth",
            "gender",
            "mobile",
            "alternate_mobile",
            "personal_email",
            "address",
            "state",
            "district",
            "taluka",
            "pincode",
            "designation",
            "department",
            "joining_date",
            "employment_status",
            "resignation_date",
            "emergency_contact_name",
            "emergency_contact_number",
            "emergency_contact_relation",
            "pf_uan",
            "esi_ip_number",
            "pan_number",
            "work_state",
            "tax_regime",
            "bank_account_number",
            "bank_ifsc",
            "bank_name",
            "bank_branch",
            "upi_id",
            "create_user",
        ]

    def create(self, validated_data):
        validated_data.pop("create_user", False)
        return super().create(validated_data)


# =========================================================
# EMPLOYEE LIST SERIALIZER
# =========================================================
class EmployeeListSerializer(EmployeeOrgLinksMixin, serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    work_state_name = serializers.CharField(source="work_state.state_name", read_only=True, allow_null=True)
    documents = EmployeeDocumentSerializer(many=True, read_only=True)
    has_user_account = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            'id',
            'employee_code',
            'full_name',
            'first_name',
            'middle_name',
            'last_name',
            'date_of_birth',
            'gender',
            'mobile',
            'alternate_mobile',
            'personal_email',
            'address',
            'state',
            'district',
            'taluka',
            'pincode',
            'designation',
            'department',
            'joining_date',
            'employment_status',
            'resignation_date',
            'emergency_contact_name',
            'emergency_contact_number',
            'emergency_contact_relation',
            'profile_photo',
            "pf_uan",
            "esi_ip_number",
            "pan_number",
            "work_state",
            "work_state_name",       # SerializerMethodField or CharField source
            "tax_regime",
            "bank_account_number",
            "bank_ifsc",
            "bank_name",
            "bank_branch",
            "upi_id",
            'documents',
            'is_active',
            'created_at',
            'has_user_account',
            *EmployeeOrgLinksMixin.ORG_LINK_FIELDS,
        ]

    def get_full_name(self, obj):
        parts = [obj.first_name, obj.middle_name, obj.last_name]
        return " ".join(part.strip() for part in parts if part)

    def get_has_user_account(self, obj):
        return obj.user_id is not None


# =========================================================
# EMPLOYEE DETAIL SERIALIZER
# =========================================================
class EmployeeDetailSerializer(EmployeeOrgLinksMixin, serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    work_state_name = serializers.CharField(source="work_state.state_name", read_only=True, allow_null=True)
    documents = EmployeeDocumentSerializer(many=True, read_only=True)
    has_user_account = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            'id',
            'employee_code',
            'full_name',
            'first_name',
            'middle_name',
            'last_name',
            'date_of_birth',
            'gender',
            'mobile',
            'alternate_mobile',
            'personal_email',
            'address',
            'state',
            'district',
            'taluka',
            'pincode',
            'designation',
            'department',
            'joining_date',
            'employment_status',
            'resignation_date',
            'emergency_contact_name',
            'emergency_contact_number',
            'emergency_contact_relation',
            'profile_photo',
            "pf_uan",
            "esi_ip_number",
            "pan_number",
            "work_state",
            "work_state_name",       # SerializerMethodField or CharField source
            "tax_regime",
            "bank_account_number",
            "bank_ifsc",
            "bank_name",
            "bank_branch",
            "upi_id",
            'documents',
            'is_active',
            'created_at',
            'updated_at',
            'has_user_account',
            *EmployeeOrgLinksMixin.ORG_LINK_FIELDS,
        ]

    def get_full_name(self, obj):
        parts = [obj.first_name, obj.middle_name, obj.last_name]
        return " ".join(part.strip() for part in parts if part)

    def get_has_user_account(self, obj):
        return obj.user_id is not None


# =========================================================
# EMPLOYEE UPDATE SERIALIZER
# =========================================================
class EmployeeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = [
            'first_name',
            'middle_name',
            'last_name',
            'date_of_birth',
            'gender',
            'mobile',
            'alternate_mobile',
            'personal_email',
            'address',
            'state',
            'district',
            'taluka',
            'pincode',
            'designation',
            'department',
            'joining_date',
            'employment_status',
            'resignation_date',
            'emergency_contact_name',
            'emergency_contact_number',
            'emergency_contact_relation',
            "pf_uan",
            "esi_ip_number",
            "pan_number",
            "work_state",
            "tax_regime",
            "bank_account_number",
            "bank_ifsc",
            "bank_name",
            "bank_branch",
            "upi_id",
        ]
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
        }



# =========================================================
# EMPLOYEE SELF-SERVICE PROFILE SERIALIZER
# =========================================================
class MyEmployeeProfileSerializer(EmployeeOrgLinksMixin, serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    work_state_name = serializers.CharField(
        source="work_state.state_name",
        read_only=True,
        allow_null=True,
    )
    documents = EmployeeDocumentSerializer(many=True, read_only=True)
    organization_name = serializers.CharField(
        source="organization.organization_name",
        read_only=True,
        allow_null=True,
    )
    has_user_account = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_code",
            "full_name",
            "first_name",
            "middle_name",
            "last_name",
            "date_of_birth",
            "gender",
            "mobile",
            "alternate_mobile",
            "personal_email",
            "address",
            "state",
            "district",
            "taluka",
            "pincode",
            "designation",
            "department",
            "joining_date",
            "employment_status",
            "resignation_date",
            "emergency_contact_name",
            "emergency_contact_number",
            "emergency_contact_relation",
            "profile_photo",
            "pf_uan",
            "esi_ip_number",
            "pan_number",
            "work_state",
            "work_state_name",
            "tax_regime",
            "bank_account_number",
            "bank_ifsc",
            "bank_name",
            "bank_branch",
            "upi_id",
            "documents",
            "organization",
            "organization_name",
            "has_user_account",
            "is_active",
            "created_at",
            "updated_at",
            *EmployeeOrgLinksMixin.ORG_LINK_FIELDS,
        ]
        read_only_fields = fields   # everything is read-only here

    def get_full_name(self, obj):
        parts = [obj.first_name, obj.middle_name, obj.last_name]
        return " ".join(part.strip() for part in parts if part)

    def get_has_user_account(self, obj):
        return obj.user_id is not None
