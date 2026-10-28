from django.urls import path

from .views import (
    EmployeeCreateAPIView,
    EmployeeUserCreateAPIView,
    EmployeeListAPIView,
    EmployeeDetailAPIView,
    EmployeeUpdateAPIView,
    EmployeeDeactivateAPIView,
    EmployeeDocumentUploadAPIView,
    EmployeeDocumentDeleteAPIView,
)

urlpatterns = [

    # =====================================================
    # EMPLOYEE
    # =====================================================
    path("create/", EmployeeCreateAPIView.as_view(), name="employee-create"),
    path("create-user/", EmployeeUserCreateAPIView.as_view(), name="employee-create-user"),
    path("list/", EmployeeListAPIView.as_view(), name="employee-list"),
    path("detail/", EmployeeDetailAPIView.as_view(), name="employee-detail"),
    path("update/", EmployeeUpdateAPIView.as_view(), name="employee-update"),
    path("deactivate/", EmployeeDeactivateAPIView.as_view(), name="employee-deactivate"),

    # =====================================================
    # EMPLOYEE DOCUMENTS
    # =====================================================
    path("document/upload/", EmployeeDocumentUploadAPIView.as_view(), name="employee-document-upload"),
    path("document/delete/", EmployeeDocumentDeleteAPIView.as_view(), name="employee-document-delete"),
]