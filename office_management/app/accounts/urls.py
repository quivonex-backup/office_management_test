from django.urls import path
from .views import (
    RegisterAPIView, LoginAPIView, ChangePasswordAPIView, ForgotPasswordAPIView,
    MyProfileAPIView,MyProfileUpdateAPIView,
    SendOTPAPIView, VerifyOTPAPIView,
    UserListAPIView, UserDetailAPIView, UserUpdateAPIView, UserDeactivateAPIView,
    RoleCreateAPIView, RoleListAPIView, RoleDetailAPIView, RoleUpdateAPIView, RoleDeleteAPIView,
    OrganizationCreateAPIView, OrganizationListAPIView, OrganizationDetailAPIView,
    OrganizationUpdateAPIView, OrganizationDeactivateAPIView,
    OrganizationAssignOwnerAPIView, OrganizationAssignUserAPIView, MyOrganizationsAPIView,
)

urlpatterns = [
    # Authentication
    path("register/", RegisterAPIView.as_view()),
    path("login/", LoginAPIView.as_view()),
    path("change-password/", ChangePasswordAPIView.as_view()),
    path("forgot-password/", ForgotPasswordAPIView.as_view()),

    path("my-profile/", MyProfileAPIView.as_view()),
    path("my-profile/update/", MyProfileUpdateAPIView.as_view()),

    # OTP
    path("send-otp/", SendOTPAPIView.as_view()),
    path("verify-otp/", VerifyOTPAPIView.as_view()),

    # Users
    path("user/list/", UserListAPIView.as_view()),
    path("user/detail/", UserDetailAPIView.as_view()),
    path("user/update/", UserUpdateAPIView.as_view()),
    path("user/deactivate/", UserDeactivateAPIView.as_view()),

    # Roles
    path("role/create/", RoleCreateAPIView.as_view()),
    path("role/list/", RoleListAPIView.as_view()),
    path("role/detail/", RoleDetailAPIView.as_view()),
    path("role/update/", RoleUpdateAPIView.as_view()),
    path("role/delete/", RoleDeleteAPIView.as_view()),

    # Organizations
    path("organization/create/", OrganizationCreateAPIView.as_view()),
    path("organization/list/", OrganizationListAPIView.as_view()),
    path("organization/detail/", OrganizationDetailAPIView.as_view()),
    path("organization/update/", OrganizationUpdateAPIView.as_view()),
    path("organization/deactivate/", OrganizationDeactivateAPIView.as_view()),

    path("organization/assign-owner/", OrganizationAssignOwnerAPIView.as_view()),
    path("organization/assign-user/", OrganizationAssignUserAPIView.as_view()),
    path("organization/my-organizations/", MyOrganizationsAPIView.as_view()),
   
]