from django.contrib.auth.password_validation import validate_password
from django.conf import settings
from rest_framework import serializers
from .models import User, Role, EmailOTP, Organization, DatabaseBackup


# ---------- Role ----------
class RoleSerializer(serializers.ModelSerializer):

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate_name(self, value):
        value = value.strip()
        queryset = Role.objects.filter(name__iexact=value)
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)
        if queryset.exists():
            raise serializers.ValidationError("Role already exists.")
        return value


# ---------- User (read-only) ----------
class UserSerializer(serializers.ModelSerializer):
    role_details = RoleSerializer(source="role", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "mobile",
            "profile_photo",
            "role",
            "role_details",
            "is_active",
            "date_joined",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "date_joined", "created_at", "updated_at"]


# ---------- User creation ----------
class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "mobile",
            "profile_photo",
            "role",
            "password",
            "confirm_password",
        ]

    def validate_username(self, value):
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                "Username already exists."
            )
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "Email already exists."
            )
        return value

    def validate_mobile(self, value):
        value = value.strip()
        if User.objects.filter(mobile=value).exists():
            raise serializers.ValidationError(
                "Mobile number already exists."
            )
        return value

    def validate_role(self, value):
        if value and not value.is_active:
            raise serializers.ValidationError(
                "Selected role is inactive."
            )
        return value

    def validate(self, attrs):
        password = attrs.get("password")
        confirm_password = attrs.get("confirm_password")
        if password != confirm_password:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        password = validated_data.pop("password")
        user = User(**validated_data)
        # Never save plain password directly
        user.set_password(password)
        user.save()
        return user


# ---------- User update ----------
class UserUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "mobile",
            "profile_photo",
            "role",
            "is_active",
        ]

    def validate_email(self, value):
        value = value.strip().lower()
        queryset = User.objects.filter(email__iexact=value)
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)
        if queryset.exists():
            raise serializers.ValidationError("Email already exists.")
        return value

    def validate_mobile(self, value):
        value = value.strip()
        queryset = User.objects.filter(mobile=value)
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)
        if queryset.exists():
            raise serializers.ValidationError("Mobile number already exists.")
        return value


# ---------- My Profile Update ----------
class MyProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "mobile",
            "profile_photo",
        ]

    def validate_email(self, value):
        value = value.strip().lower()

        queryset = User.objects.filter(email__iexact=value)

        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)

        if queryset.exists():
            raise serializers.ValidationError("Email already exists.")

        return value

    def validate_mobile(self, value):
        value = value.strip()

        queryset = User.objects.filter(mobile=value)

        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)

        if queryset.exists():
            raise serializers.ValidationError("Mobile number already exists.")

        return value


# ---------- Email OTP ----------
class EmailOTPSerializer(serializers.ModelSerializer):

    class Meta:
        model = EmailOTP

        fields = [
            "id",
            "email",
            "purpose",
            "is_verified",
            "attempts",
            "expires_at",
            "verified_at",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "is_verified",
            "attempts",
            "expires_at",
            "verified_at",
            "created_at",
        ]


# ---------- Send OTP ----------
class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    purpose = serializers.ChoiceField(
        choices=EmailOTP.PURPOSE_CHOICES,
        required=False,
        allow_null=True,
    )


# ---------- Verify OTP ----------
class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.RegexField(
        regex=r"^\d{6}$",
        write_only=True,
        error_messages={
            "invalid": "OTP must contain exactly 6 digits."
        }
    )
    purpose = serializers.ChoiceField(
        choices=EmailOTP.PURPOSE_CHOICES,
        required=False,
        allow_null=True,
    )


# ---------- Forget Password ----------
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    new_password = serializers.CharField(
        write_only=True,
        validators=[validate_password]
    )
    confirm_password = serializers.CharField(
        write_only=True
    )

    def validate_email(self, value):
        value = value.strip().lower()

        if not User.objects.filter(email__iexact=value, is_active=True).exists():
            raise serializers.ValidationError(
                "User with this email does not exist."
            )
        return value

    def validate(self, attrs):
        new_password = attrs.get("new_password")
        confirm_password = attrs.get("confirm_password")

        if new_password != confirm_password:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        return attrs



# ---------- Organization ----------
class OrganizationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Organization
        fields = [
            "id",
            "organization_name",
            "legal_name",
            "organization_code",
            "business_type",
            "industry",
            "description",
            "registration_number",
            "gst_number",
            "pan_number",
            "cin_number",
            "email",
            "phone_number",
            "alternate_phone_number",
            "website",
            "address_line_1",
            "address_line_2",
            "city",
            "district",
            "state",
            "pincode",
            "country",
            "latitude",
            "longitude",
            "logo",
            "owner",
            "created_by",
            "updated_by",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "organization_code",
            "owner",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]



# ---------- Database Backup ----------
class DatabaseBackupSerializer(serializers.ModelSerializer):

    file_name = serializers.SerializerMethodField()
    storage_key = serializers.FileField(source="file", read_only=True)
    file_size_mb = serializers.SerializerMethodField()

    class Meta:
        model = DatabaseBackup
        fields = [
            "id",
            "file_name",
            "storage_key",
            "file_size",
            "file_size_mb",
            "created_by",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "file_name",
            "storage_key",
            "file_size",
            "file_size_mb",
            "created_by",
            "created_at",
        ]

    def get_file_name(self, obj):
        import os
        return os.path.basename(obj.file.name)

    # def get_storage_key(self, obj):
    #     return obj.file.name

    def get_file_size_mb(self, obj):
        return round(obj.file_size / (1024 * 1024), 2)


# ---------- Database Backup Download ----------
class DatabaseBackupDownloadSerializer(serializers.Serializer):

    id = serializers.IntegerField(min_value=1)


# ---------- Database Backup Restore ----------
class DatabaseBackupRestoreSerializer(serializers.Serializer):

    file = serializers.FileField()

    confirmation = serializers.CharField()

    def validate_file(self, value):

        if not value.name.lower().endswith(".sql"):
            raise serializers.ValidationError(
                "Only .sql files are accepted."
            )

        if value.size <= 0:
            raise serializers.ValidationError(
                "Uploaded SQL file is empty."
            )

        max_size = getattr(
            settings,
            "DATABASE_BACKUP_MAX_UPLOAD_SIZE",
            2 * 1024 * 1024 * 1024,
        )

        if value.size > max_size:
            raise serializers.ValidationError(
                "Uploaded SQL file exceeds the allowed size."
            )

        return value

    def validate_confirmation(self, value):

        if value != "RESTORE DATABASE":
            raise serializers.ValidationError(
                "Please enter RESTORE DATABASE to confirm."
            )

        return value


# =========================================================
# BATCH 1: BRANCH / ACCESS ROLE / PERMISSION
# =========================================================
from .models import Branch, AccessRole, Permission  # noqa: E402
from .permission_catalog import ALL_CODES  # noqa: E402
from app.location_master.models import StateMaster  # noqa: E402


class _OrgUniqueNameMixin:
    """Case-insensitive unique `name` within context['organization']."""

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Name is required.")
        organization = self.context["organization"]
        qs = self.Meta.model.objects.filter(organization=organization, name__iexact=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This name already exists in your organization.")
        return value


class BranchSerializer(serializers.ModelSerializer):
    state_id = serializers.IntegerField(source="state.id", read_only=True, allow_null=True)
    state_name = serializers.CharField(source="state.state_name", read_only=True, allow_null=True)
    employee_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Branch
        fields = [
            "id", "name", "code", "address", "city", "state_id", "state_name",
            "latitude", "longitude", "allowed_radius_meters",
            "is_active", "employee_count", "created_at", "updated_at",
        ]


class BranchWriteSerializer(_OrgUniqueNameMixin, serializers.ModelSerializer):
    state_id = serializers.PrimaryKeyRelatedField(
        source="state", queryset=StateMaster.objects.filter(is_active=True),
        required=False, allow_null=True,
    )

    class Meta:
        model = Branch
        fields = [
            "name", "code", "address", "city", "state_id",
            "latitude", "longitude", "allowed_radius_meters",
        ]

    def validate(self, attrs):
        lat = attrs.get("latitude", getattr(self.instance, "latitude", None))
        lng = attrs.get("longitude", getattr(self.instance, "longitude", None))
        if (lat is None) != (lng is None):
            raise serializers.ValidationError(
                {"latitude": "Send latitude and longitude together, or neither."}
            )
        if lat is not None and not (-90 <= lat <= 90):
            raise serializers.ValidationError({"latitude": "Latitude must be between -90 and 90."})
        if lng is not None and not (-180 <= lng <= 180):
            raise serializers.ValidationError({"longitude": "Longitude must be between -180 and 180."})
        return attrs


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["code", "group", "label"]


class AccessRoleSerializer(serializers.ModelSerializer):
    permission_codes = serializers.SerializerMethodField()
    employee_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = AccessRole
        fields = [
            "id", "name", "description", "is_active",
            "permission_codes", "employee_count", "created_at", "updated_at",
        ]

    def get_permission_codes(self, obj):
        return sorted(p.code for p in obj.permissions.all())


class AccessRoleWriteSerializer(_OrgUniqueNameMixin, serializers.ModelSerializer):
    permission_codes = serializers.ListField(
        child=serializers.ChoiceField(choices=ALL_CODES), required=False, allow_empty=True,
    )

    class Meta:
        model = AccessRole
        fields = ["name", "description", "permission_codes"]

    def validate_permission_codes(self, value):
        return sorted(set(value))
