from django.urls import path

from .views import (
    # Super Admin — Statutory Rate Configs
    StatutoryRateConfigListAPIView,
    StatutoryRateConfigCreateAPIView,
    StatutoryRateConfigUpdateAPIView,

    # Super Admin — Statutory Slabs
    StatutorySlabListAPIView,
    StatutorySlabCreateAPIView,
    StatutorySlabUpdateAPIView,

    # Org Admin — Settings
    PayrollSettingsAPIView,
    CompanyStatutorySettingsAPIView,

    # Org Admin — Salary Components
    SalaryComponentListAPIView,
    SalaryComponentCreateAPIView,

    # Org Admin — Salary Structures
    SalaryStructureListAPIView,
    SalaryStructureCreateAPIView,
    SalaryStructureDetailAPIView,
    SalaryStructureUpdateAPIView,
    SalaryStructureDeactivateAPIView,

    # Org Admin — Salary Assignments
    SalaryAssignmentListAPIView,
    SalaryAssignmentCreateAPIView,
    SalaryAssignmentUpdateAPIView,
    SalaryAssignmentBulkAssignAPIView,
    SalaryAssignmentBulkCloseAPIView,

    # Org Admin — Payroll Runs
    PayrollRunPreviewAPIView,
    PayrollRunCreateAPIView,
    PayrollRunListAPIView,
    PayrollRunDetailAPIView,
    PayrollRunGenerateAPIView,
    PayrollRunFinalizeAPIView,

    # Org Admin — Payroll Records
    PayrollRecordListAPIView,
    PayrollRecordUpdateDeductionsAPIView,

    # Org Admin — Payments
    PaymentRecordAPIView,
    PaymentBulkRecordForRunAPIView,
    PaymentListAPIView,

    # Employee
    MyPayslipListAPIView,
    MyPayslipDetailAPIView,
    MySalaryAssignmentAPIView,
)


urlpatterns = [
    # =========================================================
    # SUPER ADMIN — STATUTORY RATE CONFIGS
    # =========================================================
    path("statutory-rate-configs/list/", StatutoryRateConfigListAPIView.as_view()),
    path("statutory-rate-configs/create/", StatutoryRateConfigCreateAPIView.as_view()),
    path("statutory-rate-configs/update/", StatutoryRateConfigUpdateAPIView.as_view()),

    # =========================================================
    # SUPER ADMIN — STATUTORY SLABS
    # =========================================================
    path("statutory-slabs/list/", StatutorySlabListAPIView.as_view()),
    path("statutory-slabs/create/", StatutorySlabCreateAPIView.as_view()),
    path("statutory-slabs/update/", StatutorySlabUpdateAPIView.as_view()),

    # =========================================================
    # ORG ADMIN — SETTINGS
    # =========================================================
    path("settings/", PayrollSettingsAPIView.as_view()),
    path("statutory-settings/", CompanyStatutorySettingsAPIView.as_view()),

    # =========================================================
    # ORG ADMIN — SALARY COMPONENTS
    # =========================================================
    path("components/list/", SalaryComponentListAPIView.as_view()),
    path("components/create/", SalaryComponentCreateAPIView.as_view()),

    # =========================================================
    # ORG ADMIN — SALARY STRUCTURES
    # =========================================================
    path("structures/list/", SalaryStructureListAPIView.as_view()),
    path("structures/create/", SalaryStructureCreateAPIView.as_view()),
    path("structures/detail/", SalaryStructureDetailAPIView.as_view()),
    path("structures/update/", SalaryStructureUpdateAPIView.as_view()),
    path("structures/deactivate/", SalaryStructureDeactivateAPIView.as_view()),

    # =========================================================
    # ORG ADMIN — SALARY ASSIGNMENTS
    # =========================================================
    path("assignments/list/", SalaryAssignmentListAPIView.as_view()),
    path("assignments/create/", SalaryAssignmentCreateAPIView.as_view()),
    path("assignments/update/", SalaryAssignmentUpdateAPIView.as_view()),
    path("assignments/bulk-assign/", SalaryAssignmentBulkAssignAPIView.as_view()),
    path("assignments/bulk-close/", SalaryAssignmentBulkCloseAPIView.as_view()),

    # =========================================================
    # ORG ADMIN — PAYROLL RUNS
    # =========================================================
    path("runs/preview/", PayrollRunPreviewAPIView.as_view()),
    path("runs/create/", PayrollRunCreateAPIView.as_view()),
    path("runs/list/", PayrollRunListAPIView.as_view()),
    path("runs/detail/", PayrollRunDetailAPIView.as_view()),
    path("runs/generate/", PayrollRunGenerateAPIView.as_view()),
    path("runs/finalize/", PayrollRunFinalizeAPIView.as_view()),

    # =========================================================
    # ORG ADMIN — PAYROLL RECORDS
    # =========================================================
    path("records/list/", PayrollRecordListAPIView.as_view()),
    path("records/update-deductions/", PayrollRecordUpdateDeductionsAPIView.as_view()),

    # =========================================================
    # ORG ADMIN — PAYMENTS
    # =========================================================
    path("payments/record/", PaymentRecordAPIView.as_view()),
    path("payments/bulk-record/", PaymentBulkRecordForRunAPIView.as_view()),
    path("payments/list/", PaymentListAPIView.as_view()),

    # =========================================================
    # EMPLOYEE
    # =========================================================
    path("my/payslips/", MyPayslipListAPIView.as_view()),
    path("my/payslips/detail/", MyPayslipDetailAPIView.as_view()),
    path("my/salary/", MySalaryAssignmentAPIView.as_view()),
]
