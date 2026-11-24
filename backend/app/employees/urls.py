from django.urls import path

from .views import (
    EmployeeCreateAPIView,
    EmployeeUserCreateAPIView,
    EmployeeListAPIView,
    EmployeeDetailAPIView,
    EmployeeUpdateAPIView,
    EmployeeDeactivateAPIView,
    EmployeeReactivateAPIView,
    EmployeeDocumentUploadAPIView,
    EmployeeDocumentDeleteAPIView,
    MyEmployeeProfileAPIView,
)
from .views import (
    DepartmentListAPIView, DepartmentCreateAPIView, DepartmentUpdateAPIView, DepartmentDeactivateAPIView,
    DesignationListAPIView, DesignationCreateAPIView, DesignationUpdateAPIView, DesignationDeactivateAPIView,
)

# ---------------------------------------------------------------------------
# Who calls what:
#   #SU  super admin (platform)        #A  organization admin side
#   #E   employee self-service         #PUB public (no token)   #DEV debug only
#   perm: <code>  enforced permission code (organization owner always passes;
#                 others need an access role that has the code)
# ---------------------------------------------------------------------------
urlpatterns = [

    # =====================================================
    # EMPLOYEE
    # =====================================================
    path("create/", EmployeeCreateAPIView.as_view(), name="employee-create"),                                  #A  perm: employee.update (+ employee.create_user if create_user)
    path("create-user/", EmployeeUserCreateAPIView.as_view(), name="employee-create-user"),                    #A  perm: employee.create_user
    path("list/", EmployeeListAPIView.as_view(), name="employee-list"),                                        #A  scope: self|team|all (employee.view_*)
    path("detail/", EmployeeDetailAPIView.as_view(), name="employee-detail"),                                  #A  own, or in team/all scope
    path("update/", EmployeeUpdateAPIView.as_view(), name="employee-update"),                                  #A  perm: employee.update (access_role_id needs access.manage)
    path("deactivate/", EmployeeDeactivateAPIView.as_view(), name="employee-deactivate"),                      #A  perm: employee.update  closes running shift / salary assignments (last_working_day)
    path("reactivate/", EmployeeReactivateAPIView.as_view(), name="employee-reactivate"),                      #A  perm: employee.update  rehire: employee + membership + login back on (shift / salary assigned again)

    # =====================================================
    # EMPLOYEE DOCUMENTS
    # =====================================================
    path("document/upload/", EmployeeDocumentUploadAPIView.as_view(), name="employee-document-upload"),        #A  perm: employee.update
    path("document/delete/", EmployeeDocumentDeleteAPIView.as_view(), name="employee-document-delete"),        #A  perm: employee.update

    # =====================================================
    # EMPLOYEE SELF-SERVICE
    # =====================================================
    path("my-profile/", MyEmployeeProfileAPIView.as_view(), name="employee-my-profile"),                       #E

    # =====================================================
    # ORGANIZATION MASTERS (batch 1)
    # =====================================================
    path("department/list/", DepartmentListAPIView.as_view(), name="department-list"),                         #E #A
    path("department/create/", DepartmentCreateAPIView.as_view(), name="department-create"),                   #A  perm: org.manage
    path("department/update/", DepartmentUpdateAPIView.as_view(), name="department-update"),                   #A  perm: org.manage
    path("department/deactivate/", DepartmentDeactivateAPIView.as_view(), name="department-deactivate"),       #A  perm: org.manage
    path("designation/list/", DesignationListAPIView.as_view(), name="designation-list"),                      #E #A
    path("designation/create/", DesignationCreateAPIView.as_view(), name="designation-create"),                #A  perm: org.manage
    path("designation/update/", DesignationUpdateAPIView.as_view(), name="designation-update"),                #A  perm: org.manage
    path("designation/deactivate/", DesignationDeactivateAPIView.as_view(), name="designation-deactivate"),    #A  perm: org.manage
]
