import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth import authenticate
from django.db import IntegrityError
from django.db import transaction
from django.utils import timezone
from django.db.models import Q

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .services import is_super_admin, send_user_registration_email
from common.s3_utils import (
    upload_to_s3,
    update_s3_file,
    delete_from_s3,
)
from common.code_generators import generate_organization_code

from .models import User, Role, EmailOTP, Organization, OrganizationMembership
from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    MyProfileUpdateSerializer,
    SendOTPSerializer,
    VerifyOTPSerializer,
    ForgotPasswordSerializer,
    RoleSerializer,
    OrganizationSerializer,
)

from app.audit.services import log_activity


# ----------------------------------------------------------------------
# AUTHENTICATION
# ----------------------------------------------------------------------

class RegisterAPIView(APIView):
    """
    API endpoint to register a new user.

    - Accepts user data and an optional profile photo.
    - Uploads the photo to S3 before creating the user.
    - Sends a welcome email with credentials.
    - Logs the action and handles failures gracefully.
    """

    # permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data.copy()
        profile_photo = request.FILES.get("profile_photo")

        # Remove file from data so the serializer doesn't try to process it
        data.pop("profile_photo", None)

        serializer = UserCreateSerializer(data=data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        plain_password = serializer.validated_data["password"]
        profile_photo_path = None

        try:
            if profile_photo:
                profile_photo_path = upload_to_s3(
                    file=profile_photo,
                    folder="users/profile"
                )

            user = serializer.save(
                profile_photo=profile_photo_path
            )

            log_activity(
                request=request,
                action="CREATE",
                module="USER",
                object_type="User",
                object_id=user.id,
                description=f"User '{user.username}' created.",
                new_data=UserSerializer(user).data,
            )

            email_sent = True
            try:
                send_user_registration_email(
                    user=user,
                    plain_password=plain_password
                )
            except Exception:
                email_sent = False

            message = "User registered successfully."
            if email_sent:
                message = (
                    "User registered successfully. "
                    "Login credentials sent to user's email."
                )
            else:
                message = (
                    "User registered successfully, "
                    "but registration email could not be sent."
                )

            return Response(
                {
                    "status": True,
                    "message": message,
                    "data": UserSerializer(user).data,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception:
            if profile_photo_path:
                delete_from_s3(profile_photo_path)

            return Response(
                {
                    "status": False,
                    "message": "Unable to register user.",
                    "data": None,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        if not username or not password:
            return Response(
                {
                    "status": False,
                    "message": "Username and password are required.",
                    "data": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = authenticate(request=request, username=username, password=password)
        if user is None:
            return Response(
                {
                    "status": False,
                    "message": "Invalid username or password.",
                    "data": None,
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not user.is_active:
            return Response(
                {
                    "status": False,
                    "message": "Your account is inactive.",
                    "data": None,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        refresh = RefreshToken.for_user(user)
        log_activity(
            request=request,
            user=user,
            action="LOGIN",
            module="AUTH",
            object_type="User",
            object_id=user.id,
            description=f"User '{user.username}' logged in successfully.",
        )
        return Response(
            {
                "status": True,
                "message": "Login successful.",
                "data": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "user": UserSerializer(user).data,
                },
            },
            status=status.HTTP_200_OK,
        )


class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        # Validate required fields
        if not old_password:
            return Response(
                {"status": False, "message": "Old password is required.", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not new_password:
            return Response(
                {"status": False, "message": "New password is required.", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not confirm_password:
            return Response(
                {"status": False, "message": "Confirm password is required.", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify old password
        if not user.check_password(old_password):
            return Response(
                {"status": False, "message": "Old password is incorrect.", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check new passwords match
        if new_password != confirm_password:
            return Response(
                {"status": False, "message": "New password and confirm password do not match.", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Prevent using the same password
        if user.check_password(new_password):
            return Response(
                {"status": False, "message": "New password cannot be the same as old password.", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Run Django password validators
        # try:
        #     validate_password(new_password, user=user)
        # except ValidationError as error:
        #     return Response(
        #         {"status": False, "message": "Password validation failed.", "errors": error.messages},
        #         status=status.HTTP_400_BAD_REQUEST,
        #     )

        # Update password
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])

        # --- Audit Logging ---
        log_activity(
            request=request,
            action="PASSWORD_CHANGE",
            module="USER",
            object_type="User",
            object_id=user.id,
            description=f"User '{user.username}' changed password.",
            # No old_data/new_data to avoid exposing passwords
        )

        return Response(
            {"status": True, "message": "Password changed successfully. Please login again.", "data": None},
            status=status.HTTP_200_OK,
        )


class ForgotPasswordAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data["email"]
        new_password = serializer.validated_data["new_password"]

        try:
            user = User.objects.get(
                email__iexact=email,
                is_active=True
            )

            user.set_password(new_password)

            user.save(
                update_fields=[
                    "password",
                    "updated_at",
                ]
            )

            log_activity(
                request=request,
                user=user,
                action="PASSWORD_RESET",
                module="AUTH",
                object_type="User",
                object_id=user.id,
                description=f"Password reset for user '{user.username}'.",
            )

            return Response(
                {
                    "status": True,
                    "message": "Password reset successfully. Please login with your new password.",
                    "data": None,
                },
                status=status.HTTP_200_OK,
            )

        except User.DoesNotExist:
            return Response(
                {
                    "status": False,
                    "message": "User not found.",
                    "data": None,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        except Exception:
            return Response(
                {
                    "status": False,
                    "message": "Unable to reset password. Please try again.",
                    "data": None,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ----------------------------------------------------------------------
# MY PROFILE
# ----------------------------------------------------------------------

class MyProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = (
            User.objects
            .select_related("role")
            .get(id=request.user.id)
        )

        return Response(
            {
                "status": True,
                "message": "Profile fetched successfully.",
                "data": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class MyProfileUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        old_data = UserSerializer(user).data.copy()

        data = request.data.copy()

        data.pop("profile_photo", None)

        old_profile_photo = (
            user.profile_photo.name
            if user.profile_photo
            else None
        )

        serializer = MyProfileUpdateSerializer(
            user,
            data=data,
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

        new_profile_photo = request.FILES.get("profile_photo")
        new_profile_photo_path = None

        try:
            if new_profile_photo:
                new_profile_photo_path = upload_to_s3(
                    file=new_profile_photo,
                    folder="users/profile"
                )

            if new_profile_photo_path:
                user = serializer.save(profile_photo=new_profile_photo_path)
            else:
                user = serializer.save()

            if (
                new_profile_photo_path
                and old_profile_photo
                and old_profile_photo != new_profile_photo_path
            ):
                delete_from_s3(old_profile_photo)

            log_activity(
                request=request,
                action="UPDATE",
                module="USER",
                object_type="User",
                object_id=user.id,
                description=f"User '{user.username}' updated own profile.",
                old_data=old_data,
                new_data=UserSerializer(user).data,
            )

            return Response(
                {
                    "status": True,
                    "message": "Profile updated successfully.",
                    "data": UserSerializer(user).data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception:
            # Delete newly uploaded file if update fails
            if new_profile_photo_path:
                delete_from_s3(new_profile_photo_path)

            return Response(
                {
                    "status": False,
                    "message": "Unable to update profile.",
                    "data": None,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ----------------------------------------------------------------------
# OTP
# ----------------------------------------------------------------------

class SendOTPAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data["email"]
        purpose = serializer.validated_data.get("purpose")

        # Expire any previous unverified OTPs for this email/purpose
        EmailOTP.objects.filter(
            email=email,
            purpose=purpose,
            is_verified=False,
            expires_at__gt=timezone.now(),
        ).update(expires_at=timezone.now())

        # Generate 6-digit OTP
        otp = f"{secrets.randbelow(1000000):06d}"

        # Create OTP record (plain text, expires in 5 minutes)
        otp_record = EmailOTP.objects.create(
            email=email,
            purpose=purpose,
            otp=otp,
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        # Send OTP via email
        try:
            send_mail(
                subject="Project Management ERP - OTP Verification",
                message=(
                    f"Your OTP is {otp}.\n\n"
                    "This OTP is valid for 5 minutes.\n"
                    "Do not share this OTP with anyone.\n\n"
                    "Project Management ERP"
                ),
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception:
            # Expire the OTP if email fails
            otp_record.expires_at = timezone.now()
            otp_record.save(update_fields=["expires_at"])
            return Response(
                {
                    "status": False,
                    "message": "Unable to send OTP. Please try again.",
                    "data": None,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "status": True,
                "message": "OTP sent successfully.",
                "data": {"expires_at": otp_record.expires_at},
            },
            status=status.HTTP_200_OK,
        )


class VerifyOTPAPIView(APIView):
    permission_classes = [AllowAny]
    MAX_ATTEMPTS = 5

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]
        purpose = serializer.validated_data.get("purpose")

        # Get the latest unverified OTP for this email/purpose
        otp_record = (
            EmailOTP.objects
            .filter(email=email, purpose=purpose, is_verified=False)
            .order_by("-created_at")
            .first()
        )

        if not otp_record:
            return Response(
                {
                    "status": False,
                    "message": "No OTP found. Please request a new OTP.",
                    "data": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check expiration
        if timezone.now() >= otp_record.expires_at:
            return Response(
                {
                    "status": False,
                    "message": "OTP has expired. Please request a new OTP.",
                    "data": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check attempt limit
        if otp_record.attempts >= self.MAX_ATTEMPTS:
            return Response(
                {
                    "status": False,
                    "message": "Maximum OTP attempts exceeded. Please request a new OTP.",
                    "data": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify OTP (plain text comparison)
        if otp_record.otp != otp:
            otp_record.attempts += 1
            otp_record.save(update_fields=["attempts"])
            remaining_attempts = max(0, self.MAX_ATTEMPTS - otp_record.attempts)
            return Response(
                {
                    "status": False,
                    "message": "Invalid OTP.",
                    "data": {"remaining_attempts": remaining_attempts},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark OTP as verified
        otp_record.is_verified = True
        otp_record.verified_at = timezone.now()
        otp_record.save(update_fields=["is_verified", "verified_at"])

        return Response(
            {
                "status": True,
                "message": "OTP verified successfully.",
                "data": None,
            },
            status=status.HTTP_200_OK,
        )


# ----------------------------------------------------------------------
# USER MANAGEMENT
# ----------------------------------------------------------------------

class UserListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        users = User.objects.filter(is_active=True).select_related("role").order_by("-id")
        serializer = UserSerializer(users, many=True)
        return Response(
            {
                "status": True,
                "message": "Accounts fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class UserDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id = request.data.get("id")
        if not user_id:
            return Response(
                {
                    "status": False,
                    "message": "Account id is required.",
                    "data": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            user = User.objects.select_related("role").get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return Response(
                {
                    "status": False,
                    "message": "Account not found.",
                    "data": None,
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {
                "status": True,
                "message": "Account fetched successfully.",
                "data": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class UserUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id = request.data.get("id")
        if not user_id:
            return Response(
                {"status": False, "message": "User id is required.", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fetch the user
        try:
            user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return Response(
                {"status": False, "message": "User not found.", "data": None},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Capture old data BEFORE any changes (for audit)
        old_data = UserSerializer(user).data.copy()

        # Prepare data for the serializer
        data = request.data.copy()
        data.pop("profile_photo", None)   # remove file field
        data.pop("id", None)              # id not needed in serializer

        # Store old photo path before it gets overwritten
        old_profile_photo = user.profile_photo.name if user.profile_photo else None

        serializer = UserUpdateSerializer(user, data=data, partial=True)
        if not serializer.is_valid():
            return Response(
                {"status": False, "message": "Validation failed.", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_profile_photo = request.FILES.get("profile_photo")
        new_profile_photo_path = None

        try:
            # Upload new photo first (if provided)
            if new_profile_photo:
                new_profile_photo_path = upload_to_s3(
                    file=new_profile_photo,
                    folder="users/profile"
                )

            # Save user with the new photo path (or without changes)
            if new_profile_photo_path:
                user = serializer.save(profile_photo=new_profile_photo_path)
            else:
                user = serializer.save()

            # After successful DB save, delete old photo (if it exists and is different)
            if new_profile_photo_path and old_profile_photo and old_profile_photo != new_profile_photo_path:
                delete_from_s3(old_profile_photo)

            # --- Audit Logging ---
            log_activity(
                request=request,
                action="UPDATE",
                module="USER",
                object_type="User",
                object_id=user.id,
                description=f"User '{user.username}' updated.",
                old_data=old_data,
                new_data=UserSerializer(user).data,
            )

            return Response(
                {"status": True, "message": "User updated successfully.", "data": UserSerializer(user).data},
                status=status.HTTP_200_OK,
            )

        except Exception:
            # If anything fails after upload, clean up the newly uploaded file
            if new_profile_photo_path:
                delete_from_s3(new_profile_photo_path)

            return Response(
                {"status": False, "message": "Unable to update user.", "data": None},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserDeactivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id = request.data.get("id")
        if not user_id:
            return Response(
                {"status": False, "message": "Account id is required.", "data": None},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return Response(
                {"status": False, "message": "Account not found or already inactive.", "data": None},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Capture old data before deactivation
        old_data = UserSerializer(user).data.copy()

        # Soft delete
        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])

        # --- Audit Logging ---
        log_activity(
            request=request,
            action="DELETE",
            module="USER",
            object_type="User",
            object_id=user.id,
            description=f"User '{user.username}' deactivated.",
            old_data=old_data,
            new_data=UserSerializer(user).data,
        )

        return Response(
            {"status": True, "message": "Account deactivated successfully.", "data": None},
            status=status.HTTP_200_OK,
        )


# ----------------------------------------------------------------------
# ROLE MANAGEMENT
# ----------------------------------------------------------------------

class RoleCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RoleSerializer(data=request.data)
        if serializer.is_valid():
            try:
                role = serializer.save()
                log_activity(
                    request=request,
                    action="CREATE",
                    module="ROLE",
                    object_type="Role",
                    object_id=role.id,
                    description=f"Role '{role.name}' created.",
                    new_data=RoleSerializer(role).data,
                )
                return Response(
                    {
                        "status": True,
                        "message": "Role created successfully.",
                        "data": RoleSerializer(role).data,
                    },
                    status=status.HTTP_201_CREATED,
                )
            except IntegrityError:
                return Response(
                    {
                        "status": False,
                        "message": "Role with this name already exists.",
                        "data": None,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return Response(
            {
                "status": False,
                "message": "Validation failed.",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


class RoleListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        roles = Role.objects.filter(is_active=True).order_by("-id")
        serializer = RoleSerializer(roles, many=True)
        return Response(
            {
                "status": True,
                "message": "Roles fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class RoleDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        role_id = request.data.get("id")
        if not role_id:
            return Response(
                {
                    "status": False,
                    "message": "Role id is required.",
                    "data": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            role = Role.objects.get(id=role_id, is_active=True)
        except Role.DoesNotExist:
            return Response(
                {
                    "status": False,
                    "message": "Role not found.",
                    "data": None,
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {
                "status": True,
                "message": "Role fetched successfully.",
                "data": RoleSerializer(role).data,
            },
            status=status.HTTP_200_OK,
        )


class RoleUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        role_id = request.data.get("id")
        if not role_id:
            return Response(
                {
                    "status": False,
                    "message": "Role id is required.",
                    "data": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            role = Role.objects.get(id=role_id, is_active=True)
        except Role.DoesNotExist:
            return Response(
                {
                    "status": False,
                    "message": "Role not found.",
                    "data": None,
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        old_data = RoleSerializer(role).data.copy()
        serializer = RoleSerializer(role, data=request.data, partial=True)
        if serializer.is_valid():
            try:
                role = serializer.save()
                log_activity(
                    request=request,
                    action="UPDATE",
                    module="ROLE",
                    object_type="Role",
                    object_id=role.id,
                    description=f"Role '{role.name}' updated.",
                    old_data=old_data,
                    new_data=RoleSerializer(role).data,
                )
                return Response(
                    {
                        "status": True,
                        "message": "Role updated successfully.",
                        "data": RoleSerializer(role).data,
                    },
                    status=status.HTTP_200_OK,
                )
            except IntegrityError:
                return Response(
                    {
                        "status": False,
                        "message": "Role with this name already exists.",
                        "data": None,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return Response(
            {
                "status": False,
                "message": "Validation failed.",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


class RoleDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        role_id = request.data.get("id")
        if not role_id:
            return Response(
                {
                    "status": False,
                    "message": "Role id is required.",
                    "data": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            role = Role.objects.get(id=role_id, is_active=True)
        except Role.DoesNotExist:
            return Response(
                {
                    "status": False,
                    "message": "Role not found or already deleted.",
                    "data": None,
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        # Soft delete
        old_data = RoleSerializer(role).data.copy()
        role.is_active = False
        role.save(update_fields=["is_active", "updated_at"])
        log_activity(
            request=request,
            action="DELETE",
            module="ROLE",
            object_type="Role",
            object_id=role.id,
            description=f"Role '{role.name}' deactivated.",
            old_data=old_data,
            new_data=RoleSerializer(role).data,
        )
        return Response(
            {
                "status": True,
                "message": "Role deleted successfully.",
                "data": None,
            },
            status=status.HTTP_200_OK,
        )


# ----------------------------------------------------------------------
# ORGANIZATION MANAGEMENT
# ----------------------------------------------------------------------


class OrganizationCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not is_super_admin(request.user):
            return Response(
                {
                    "status": False,
                    "message": "Only the super admin can create organizations.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        data = request.data.copy()
        logo = request.FILES.get("logo")
        data.pop("logo", None)

        serializer = OrganizationSerializer(data=data)

        if not serializer.is_valid():
            return Response(
                {
                    "status": False,
                    "message": "Validation failed.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        logo_path = None

        try:
            if logo:
                logo_path = upload_to_s3(
                    file=logo,
                    folder="organizations/logos",
                )

            organization = serializer.save(
                organization_code=generate_organization_code(),
                owner=None,
                created_by=request.user,
                updated_by=request.user,
                logo=logo_path,
            )

            log_activity(
                request=request,
                action="CREATE",
                module="ORGANIZATION",
                object_type="Organization",
                object_id=organization.id,
                description=(
                    f"Organization '{organization.organization_name}' created."
                ),
                new_data=OrganizationSerializer(organization).data,
            )

            return Response(
                {
                    "status": True,
                    "message": "Organization created successfully.",
                    "data": OrganizationSerializer(organization).data,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception:
            if logo_path:
                try:
                    delete_from_s3(logo_path)
                except Exception:
                    pass

            return Response(
                {
                    "status": False,
                    "message": "Unable to create organization.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )



class OrganizationListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organizations = Organization.objects.filter(is_active=True)

        if not is_super_admin(request.user):
            organizations = organizations.filter(
                Q(owner=request.user)
                | Q(
                    memberships__user=request.user,
                    memberships__is_active=True,
                )
            ).distinct()

        organizations = organizations.order_by("-id")

        serializer = OrganizationSerializer(
            organizations,
            many=True,
        )

        return Response(
            {
                "status": True,
                "message": "Organizations fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )



class OrganizationDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization_id = request.data.get("id")

        if not organization_id:
            return Response(
                {
                    "status": False,
                    "message": "Organization id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        organizations = Organization.objects.filter(is_active=True)

        if not is_super_admin(request.user):
            organizations = organizations.filter(
                Q(owner=request.user)
                | Q(
                    memberships__user=request.user,
                    memberships__is_active=True,
                )
            ).distinct()

        organization = organizations.filter(
            id=organization_id,
        ).first()

        if not organization:
            return Response(
                {
                    "status": False,
                    "message": "Organization not found or access denied.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "status": True,
                "message": "Organization fetched successfully.",
                "data": OrganizationSerializer(organization).data,
            },
            status=status.HTTP_200_OK,
        )



class OrganizationAssignOwnerAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        if not is_super_admin(request.user):
            return Response(
                {
                    "status": False,
                    "message": "Only the super admin can assign an organization owner.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        organization_id = request.data.get("organization_id")
        user_id = request.data.get("user_id")

        if not organization_id or not user_id:
            return Response(
                {
                    "status": False,
                    "message": "organization_id and user_id are required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization = Organization.objects.select_for_update().filter(
            id=organization_id,
            is_active=True,
        ).first()

        if not organization:
            return Response(
                {
                    "status": False,
                    "message": "Organization not found or inactive.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        user = User.objects.select_for_update().filter(
            id=user_id,
            is_active=True,
        ).first()

        if not user:
            return Response(
                {
                    "status": False,
                    "message": "User not found or inactive.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        admin_role = Role.objects.filter(
            name__iexact="Admin",
            is_active=True,
        ).first()

        accountant_role = Role.objects.filter(
            name__iexact="Accountant",
            is_active=True,
        ).first()

        if not admin_role or not accountant_role:
            return Response(
                {
                    "status": False,
                    "message": (
                        "Active Admin and Accountant roles must exist."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # A user may not belong to another active organization.
        other_membership = OrganizationMembership.objects.filter(
            user=user,
            is_active=True,
            organization__is_active=True,
        ).exclude(
            organization_id=organization.id,
        ).first()

        if other_membership:
            return Response(
                {
                    "status": False,
                    "message": (
                        "This user already belongs to another active organization."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_owner_id = organization.owner_id

        # If ownership is changing, downgrade the previous owner.
        if old_owner_id and old_owner_id != user.id:
            previous_owner = User.objects.select_for_update().filter(
                id=old_owner_id,
            ).first()

            if previous_owner:
                previous_owner.role = accountant_role
                previous_owner.save(update_fields=["role"])

                # Keep the previous owner's membership active.
                OrganizationMembership.objects.filter(
                    organization=organization,
                    user_id=old_owner_id,
                ).update(
                    is_active=True,
                    updated_at=timezone.now(),
                )

        # Assign Admin role to the new owner.
        user.role = admin_role
        user.save(update_fields=["role"])

        organization.owner = user
        organization.updated_by = request.user
        organization.save(
            update_fields=["owner", "updated_by", "updated_at"]
        )

        # Create/reactivate the membership; no role is stored here.
        membership, created = OrganizationMembership.objects.update_or_create(
            organization=organization,
            user=user,
            defaults={"is_active": True},
        )

        log_activity(
            request=request,
            action="UPDATE",
            module="ORGANIZATION",
            object_type="Organization",
            object_id=organization.id,
            description=(
                f"Owner assigned to organization "
                f"'{organization.organization_name}'."
            ),
            old_data={"owner_id": old_owner_id},
            new_data={
                "owner_id": user.id,
                "owner_username": user.username,
                "role": admin_role.name,
                "membership_id": membership.id,
            },
        )

        return Response(
            {
                "status": True,
                "message": "Organization owner assigned successfully.",
                "data": {
                    "organization_id": organization.id,
                    "organization_name": organization.organization_name,
                    "owner_id": user.id,
                    "owner_username": user.username,
                    "owner_email": user.email,
                    "role_id": admin_role.id,
                    "role": admin_role.name,
                    "membership_id": membership.id,
                    "membership_created": created,
                },
            },
            status=status.HTTP_200_OK,
        )


class OrganizationAssignUserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        organization_id = request.data.get("organization_id")
        user_id = request.data.get("user_id")
        role_id = request.data.get("role_id")

        if not organization_id or not user_id or not role_id:
            return Response(
                {
                    "status": False,
                    "message": (
                        "organization_id, user_id and role_id are required."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization = Organization.objects.filter(
            id=organization_id,
            is_active=True,
        ).first()

        if not organization:
            return Response(
                {
                    "status": False,
                    "message": "Organization not found or inactive.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # -------------------------------------------------
        # PERMISSION CHECK
        # Super admin OR the organization's owner (Admin) may assign.
        # -------------------------------------------------
        is_org_owner = organization.owner_id == request.user.id

        if not is_super_admin(request.user) and not is_org_owner:
            return Response(
                {
                    "status": False,
                    "message": (
                        "Only the super admin or the organization owner "
                        "can assign organization members."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        user = User.objects.select_for_update().filter(
            id=user_id,
            is_active=True,
        ).first()

        if not user:
            return Response(
                {
                    "status": False,
                    "message": "User not found or inactive.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        role = Role.objects.filter(
            id=role_id,
            is_active=True,
        ).first()

        if not role:
            return Response(
                {
                    "status": False,
                    "message": "Role not found or inactive.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Admin is reserved for organization owners.
        if role.name.strip().lower() == "admin":
            return Response(
                {
                    "status": False,
                    "message": (
                        "The Admin role is reserved for organization owners. "
                        "Use the owner assignment API instead."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # The owner must be changed through the owner assignment API.
        if organization.owner_id == user.id:
            return Response(
                {
                    "status": False,
                    "message": (
                        "This user is the organization owner. "
                        "Use the owner assignment API to manage ownership."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Enforce one active organization per user.
        other_membership = OrganizationMembership.objects.filter(
            user=user,
            is_active=True,
            organization__is_active=True,
        ).exclude(
            organization_id=organization.id,
        ).first()

        if other_membership:
            return Response(
                {
                    "status": False,
                    "message": (
                        "This user already belongs to another active organization."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_role_name = user.role.name if user.role else None

        # Role is stored only on User.
        user.role = role
        user.save(update_fields=["role"])

        # Membership stores organization association and active status only.
        membership, created = OrganizationMembership.objects.update_or_create(
            organization=organization,
            user=user,
            defaults={"is_active": True},
        )

        log_activity(
            request=request,
            action="CREATE" if created else "UPDATE",
            module="ORGANIZATION",
            object_type="OrganizationMembership",
            object_id=membership.id,
            description=(
                f"User '{user.username}' assigned to organization "
                f"'{organization.organization_name}'."
            ),
            old_data={"role": old_role_name},
            new_data={
                "user_id": user.id,
                "username": user.username,
                "role_id": role.id,
                "role": role.name,
                "organization_id": organization.id,
                "membership_id": membership.id,
            },
        )

        return Response(
            {
                "status": True,
                "message": (
                    "Organization member assigned successfully."
                    if created
                    else "Organization member updated successfully."
                ),
                "data": {
                    "membership_id": membership.id,
                    "organization_id": organization.id,
                    "organization_name": organization.organization_name,
                    "user_id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role_id": role.id,
                    "role": role.name,
                    "is_active": membership.is_active,
                },
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class MyOrganizationsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organizations = Organization.objects.filter(
            is_active=True,
        ).filter(
            Q(owner=request.user)
            | Q(
                memberships__user=request.user,
                memberships__is_active=True,
            )
        ).distinct().order_by("-id")

        serializer = OrganizationSerializer(
            organizations,
            many=True,
        )

        return Response(
            {
                "status": True,
                "message": "Your organizations fetched successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class OrganizationUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization_id = request.data.get("id")

        if not organization_id:
            return Response(
                {
                    "status": False,
                    "message": "Organization id is required.",
                    "data": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            organization = Organization.objects.get(
                id=organization_id,
                owner=request.user,
                is_active=True,
            )
        except Organization.DoesNotExist:
            return Response(
                {
                    "status": False,
                    "message": "Organization not found.",
                    "data": None,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        old_data = OrganizationSerializer(organization).data.copy()
        old_logo_path = (
            organization.logo.name if organization.logo else None
        )

        data = request.data.copy()
        data.pop("id", None)
        data.pop("logo", None)

        serializer = OrganizationSerializer(
            organization,
            data=data,
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

        new_logo = request.FILES.get("logo")
        new_logo_path = None

        try:
            if new_logo:
                new_logo_path = upload_to_s3(
                    file=new_logo,
                    folder="organizations/logos",
                )

            save_kwargs = {
                "updated_by": request.user,
            }

            if new_logo_path:
                save_kwargs["logo"] = new_logo_path

            organization = serializer.save(**save_kwargs)

            # Delete the old logo only after the new logo is saved.
            if (
                new_logo_path
                and old_logo_path
                and old_logo_path != new_logo_path
            ):
                try:
                    delete_from_s3(old_logo_path)
                except Exception:
                    # Keep the successfully saved organization intact.
                    pass

            log_activity(
                request=request,
                action="UPDATE",
                module="ORGANIZATION",
                object_type="Organization",
                object_id=organization.id,
                description=(
                    f"Organization '{organization.organization_name}' updated."
                ),
                old_data=old_data,
                new_data=OrganizationSerializer(organization).data,
            )

            return Response(
                {
                    "status": True,
                    "message": "Organization updated successfully.",
                    "data": OrganizationSerializer(organization).data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception:
            if new_logo_path:
                try:
                    delete_from_s3(new_logo_path)
                except Exception:
                    pass

            return Response(
                {
                    "status": False,
                    "message": "Unable to update organization.",
                    "data": None,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class OrganizationDeactivateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization_id = request.data.get("id")

        if not organization_id:
            return Response(
                {
                    "status": False,
                    "message": "Organization id is required.",
                    "data": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            organization = Organization.objects.get(
                id=organization_id,
                owner=request.user,
                is_active=True,
            )
        except Organization.DoesNotExist:
            return Response(
                {
                    "status": False,
                    "message": "Organization not found or already inactive.",
                    "data": None,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        old_data = OrganizationSerializer(organization).data.copy()

        organization.is_active = False
        organization.updated_by = request.user
        organization.save(
            update_fields=["is_active", "updated_by", "updated_at"]
        )

        log_activity(
            request=request,
            action="DELETE",
            module="ORGANIZATION",
            object_type="Organization",
            object_id=organization.id,
            description=(
                f"Organization '{organization.organization_name}' deactivated."
            ),
            old_data=old_data,
            new_data=OrganizationSerializer(organization).data,
        )

        return Response(
            {
                "status": True,
                "message": "Organization deactivated successfully.",
                "data": None,
            },
            status=status.HTTP_200_OK,
        )
