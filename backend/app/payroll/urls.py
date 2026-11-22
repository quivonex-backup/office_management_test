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

    # Org Admin — Payslip Download
    PayrollPayslipDownloadAPIView,

    PayrollCalculatorAPIView,

    # Employee
    MyPayslipListAPIView,
    MyPayslipDetailAPIView,
    MySalaryAssignmentAPIView,
    MyPayslipDownloadAPIView,
)


# ---------------------------------------------------------------------------
# Who calls what:
#   #SU  super admin (platform)        #A  organization admin side
#   #E   employee self-service         #PUB public (no token)   #DEV debug only
#   perm: <code>  enforced permission code (organization owner always passes;
#                 others need an access role that has the code)
# ---------------------------------------------------------------------------
urlpatterns = [
    # =========================================================
    # SUPER ADMIN — STATUTORY RATE CONFIGS
    # =========================================================
    path("statutory-rate-configs/list/", StatutoryRateConfigListAPIView.as_view()),        #SU
    path("statutory-rate-configs/create/", StatutoryRateConfigCreateAPIView.as_view()),    #SU
    path("statutory-rate-configs/update/", StatutoryRateConfigUpdateAPIView.as_view()),    #SU

    # =========================================================
    # SUPER ADMIN — STATUTORY SLABS
    # =========================================================
    path("statutory-slabs/list/", StatutorySlabListAPIView.as_view()),                     #SU
    path("statutory-slabs/create/", StatutorySlabCreateAPIView.as_view()),                 #SU
    path("statutory-slabs/update/", StatutorySlabUpdateAPIView.as_view()),                 #SU

    # =========================================================
    # ORG ADMIN — SETTINGS
    # =========================================================
    path("settings/", PayrollSettingsAPIView.as_view()),                                   #A  perm: settings.manage, payroll.generate (any)
    path("statutory-settings/", CompanyStatutorySettingsAPIView.as_view()),                #A  perm: settings.manage, payroll.generate (any)

    # =========================================================
    # ORG ADMIN — SALARY COMPONENTS
    # =========================================================
    path("components/list/", SalaryComponentListAPIView.as_view()),                        #A  perm: salary.assign, payroll.generate (any)
    path("components/create/", SalaryComponentCreateAPIView.as_view()),                    #A  perm: salary.assign, payroll.generate (any)

    # =========================================================
    # ORG ADMIN — SALARY STRUCTURES
    # =========================================================
    path("structures/list/", SalaryStructureListAPIView.as_view()),                        #A  perm: salary.assign, payroll.generate (any)
    path("structures/create/", SalaryStructureCreateAPIView.as_view()),                    #A  perm: salary.assign, payroll.generate (any)
    path("structures/detail/", SalaryStructureDetailAPIView.as_view()),                    #A  perm: salary.assign, payroll.generate (any)
    path("structures/update/", SalaryStructureUpdateAPIView.as_view()),                    #A  perm: salary.assign, payroll.generate (any)
    path("structures/deactivate/", SalaryStructureDeactivateAPIView.as_view()),            #A  perm: salary.assign, payroll.generate (any)

    # =========================================================
    # ORG ADMIN — SALARY ASSIGNMENTS
    # =========================================================
    path("assignments/list/", SalaryAssignmentListAPIView.as_view()),                      #A  perm: salary.assign, payroll.view_all (any)
    path("assignments/create/", SalaryAssignmentCreateAPIView.as_view()),                  #A  perm: salary.assign  + annual_ctc / monthly_gross
    path("assignments/update/", SalaryAssignmentUpdateAPIView.as_view()),                  #A  perm: salary.assign  + annual_ctc / monthly_gross
    path("assignments/bulk-assign/", SalaryAssignmentBulkAssignAPIView.as_view()),         #A  perm: salary.assign  + annual_ctc / monthly_gross
    path("assignments/bulk-close/", SalaryAssignmentBulkCloseAPIView.as_view()),           #A  perm: salary.assign

    # =========================================================
    # ORG ADMIN — PAYROLL RUNS
    # =========================================================
    path("runs/preview/", PayrollRunPreviewAPIView.as_view()),                             #A  perm: payroll.generate
    path("runs/create/", PayrollRunCreateAPIView.as_view()),                               #A  perm: payroll.generate
    path("runs/list/", PayrollRunListAPIView.as_view()),                                   #A  perm: payroll.view_all, payroll.generate, payroll.finalize (any)
    path("runs/detail/", PayrollRunDetailAPIView.as_view()),                               #A  perm: payroll.view_all, payroll.generate, payroll.finalize (any)
    path("runs/generate/", PayrollRunGenerateAPIView.as_view()),                           #A  perm: payroll.generate
    path("runs/finalize/", PayrollRunFinalizeAPIView.as_view()),                           #A  perm: payroll.finalize

    # =========================================================
    # ORG ADMIN — PAYROLL RECORDS
    # =========================================================
    path("records/list/", PayrollRecordListAPIView.as_view()),                             #A  perm: payroll.view_all, payroll.generate, payroll.finalize (any)
    path("records/update-deductions/", PayrollRecordUpdateDeductionsAPIView.as_view()),    #A  perm: payroll.generate

    # =========================================================
    # ORG ADMIN — PAYMENTS
    # =========================================================
    path("payments/record/", PaymentRecordAPIView.as_view()),                              #A  perm: payroll.finalize
    path("payments/bulk-record/", PaymentBulkRecordForRunAPIView.as_view()),               #A  perm: payroll.finalize
    path("payments/list/", PaymentListAPIView.as_view()),                                  #A  perm: payroll.view_all, payroll.generate, payroll.finalize (any)

    # =========================================================
    # ORG ADMIN — PAYSLIP DOWNLOAD
    # =========================================================
    path("payslips/download/", PayrollPayslipDownloadAPIView.as_view()),                   #A  perm: payroll.view_all, payroll.generate, payroll.finalize (any)

    # =========================================================
    # ORG ADMIN — Payroll Calculator
    # =========================================================
    path("calculator/", PayrollCalculatorAPIView.as_view()),                               #A  perm: salary.assign, payroll.generate (any)  + monthly_gross / annual_ctc -> ctc_breakup

    # =========================================================
    # EMPLOYEE
    # =========================================================
    path("my/payslips/", MyPayslipListAPIView.as_view()),                                  #E
    path("my/payslips/detail/", MyPayslipDetailAPIView.as_view()),                         #E
    path("my/salary/", MySalaryAssignmentAPIView.as_view()),                               #E
    path("my/payslips/download/", MyPayslipDownloadAPIView.as_view()),                     #E
]
