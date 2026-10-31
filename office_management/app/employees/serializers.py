from rest_framework import serializers
from .models import Employee, EmployeeDocument


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
            "create_user",
        ]

    def create(self, validated_data):
        validated_data.pop("create_user", False)
        return super().create(validated_data)


# =========================================================
# EMPLOYEE LIST SERIALIZER
# =========================================================
class EmployeeListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    work_state_name = serializers.CharField(source="work_state.state_name", read_only=True, allow_null=True)
    documents = EmployeeDocumentSerializer(many=True, read_only=True)

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
            'documents',
            'is_active',
            'created_at',
        ]

    def get_full_name(self, obj):
        parts = [obj.first_name, obj.middle_name, obj.last_name]
        return " ".join(part.strip() for part in parts if part)


# =========================================================
# EMPLOYEE DETAIL SERIALIZER
# =========================================================
class EmployeeDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    work_state_name = serializers.CharField(source="work_state.state_name", read_only=True, allow_null=True)
    documents = EmployeeDocumentSerializer(many=True, read_only=True)

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
            'documents',
            'is_active',
            'created_at',
            'updated_at',
        ]

    def get_full_name(self, obj):
        parts = [obj.first_name, obj.middle_name, obj.last_name]
        return " ".join(part.strip() for part in parts if part)


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
        ]
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
        }
