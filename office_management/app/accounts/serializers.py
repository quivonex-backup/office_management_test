from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from .models import User, Role, EmailOTP, Organization


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
