from django.urls import path
from .views import (
    RegisterAPIView, LoginAPIView, RefreshTokenAPIView, ChangePasswordAPIView, ForgotPasswordAPIView,
    MyProfileAPIView,MyProfileUpdateAPIView,
    SendOTPAPIView, VerifyOTPAPIView,
    UserListAPIView, UserDetailAPIView, UserUpdateAPIView, UserDeactivateAPIView,
    RoleCreateAPIView, RoleListAPIView, RoleDetailAPIView, RoleUpdateAPIView, RoleDeleteAPIView,
    OrganizationCreateAPIView, OrganizationListAPIView, OrganizationDetailAPIView,
    OrganizationUpdateAPIView, OrganizationDeactivateAPIView,
    OrganizationAssignOwnerAPIView, OrganizationAssignUserAPIView, MyOrganizationsAPIView,
    DatabaseBackupCreateAPIView, DatabaseBackupListAPIView, DatabaseBackupDownloadAPIView, DatabaseBackupRestoreAPIView,
)
from .views import (
    BranchListAPIView, BranchCreateAPIView, BranchUpdateAPIView, BranchDeactivateAPIView,
    PermissionListAPIView,
    AccessRoleListAPIView, AccessRoleCreateAPIView, AccessRoleUpdateAPIView, AccessRoleDeactivateAPIView,
)

# ---------------------------------------------------------------------------
# Who calls what:
#   #SU  super admin (platform)        #A  organization admin side
#   #E   employee self-service         #PUB public (no token)   #DEV debug only
#   perm: <code>  enforced permission code (organization owner always passes;
#                 others need an access role that has the code)
# ---------------------------------------------------------------------------
urlpatterns = [
    # Authentication
    path("register/", RegisterAPIView.as_view()),                                    #SU
    path("login/", LoginAPIView.as_view()),                                          #E #A #SU
    path("refresh-token/", RefreshTokenAPIView.as_view()),                           #E #A #SU
    path("change-password/", ChangePasswordAPIView.as_view()),                       #E #A #SU
    path("forgot-password/", ForgotPasswordAPIView.as_view()),                       #E #A #SU

    path("my-profile/", MyProfileAPIView.as_view()),                                 #E #A #SU
    path("my-profile/update/", MyProfileUpdateAPIView.as_view()),                    #E #A #SU

    # OTP               
    path("send-otp/", SendOTPAPIView.as_view()),                                     #E #A #SU
    path("verify-otp/", VerifyOTPAPIView.as_view()),                                 #E #A #SU

    # Users             
    path("user/list/", UserListAPIView.as_view()),                                   #SU
    path("user/detail/", UserDetailAPIView.as_view()),                               #SU
    path("user/update/", UserUpdateAPIView.as_view()),                               #SU
    path("user/deactivate/", UserDeactivateAPIView.as_view()),                       #SU

    # Roles             
    path("role/create/", RoleCreateAPIView.as_view()),                               #SU
    path("role/list/", RoleListAPIView.as_view()),                                   #SU
    path("role/detail/", RoleDetailAPIView.as_view()),                               #SU
    path("role/update/", RoleUpdateAPIView.as_view()),                               #SU
    path("role/delete/", RoleDeleteAPIView.as_view()),                               #SU

    # Organizations
    path("organization/create/", OrganizationCreateAPIView.as_view()),               #SU
    path("organization/list/", OrganizationListAPIView.as_view()),                   #E #A #SU
    path("organization/detail/", OrganizationDetailAPIView.as_view()),               #E #A #SU
    path("organization/update/", OrganizationUpdateAPIView.as_view()),               #A
    path("organization/deactivate/", OrganizationDeactivateAPIView.as_view()),       #A

    path("organization/assign-owner/", OrganizationAssignOwnerAPIView.as_view()),    #SU
    path("organization/assign-user/", OrganizationAssignUserAPIView.as_view()),      #A #SU
    path("organization/my-organizations/", MyOrganizationsAPIView.as_view()),        #E #A #SU

    # DATABASE BACKUP
    path("database/backup/create/", DatabaseBackupCreateAPIView.as_view()),          #SU
    path("database/backup/list/", DatabaseBackupListAPIView.as_view()),              #SU
    path("database/backup/download/", DatabaseBackupDownloadAPIView.as_view()),      #SU
    path("database/backup/restore/", DatabaseBackupRestoreAPIView.as_view()),        #SU

    # Branches (organization level)
    path("branch/list/", BranchListAPIView.as_view()),                               #E #A
    path("branch/create/", BranchCreateAPIView.as_view()),                           #A  perm: org.manage
    path("branch/update/", BranchUpdateAPIView.as_view()),                           #A  perm: org.manage
    path("branch/deactivate/", BranchDeactivateAPIView.as_view()),                   #A  perm: org.manage

    # Access roles + permission catalog (organization level)
    path("permission/list/", PermissionListAPIView.as_view()),                       #A  perm: access.manage
    path("access-role/list/", AccessRoleListAPIView.as_view()),                      #A  perm: access.manage
    path("access-role/create/", AccessRoleCreateAPIView.as_view()),                  #A  perm: access.manage
    path("access-role/update/", AccessRoleUpdateAPIView.as_view()),                  #A  perm: access.manage
    path("access-role/deactivate/", AccessRoleDeactivateAPIView.as_view()),          #A  perm: access.manage
]
