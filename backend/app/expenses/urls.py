from django.urls import path

from .views import (
    # Expense
    ExpenseCreateAPIView,
    ExpenseListAPIView,
    ExpenseDetailAPIView,
    ExpenseUpdateAPIView,
    ExpenseDeactivateAPIView,

    # Recurring Expense
    RecurringExpenseCreateAPIView,
    RecurringExpenseListAPIView,
    RecurringExpenseDetailAPIView,
    RecurringExpenseUpdateAPIView,
    RecurringExpenseDeactivateAPIView,

    # Recurring Expense Entry
    RecurringExpenseEntryCreateAPIView,
    RecurringExpenseEntryUpdateAPIView,
    RecurringExpenseEntryDeactivateAPIView,

    # Employee Reimbursements
    EmployeeReimbursementCreateAPIView,
    EmployeeReimbursementMyListAPIView,
    EmployeeReimbursementDetailAPIView,
    EmployeeReimbursementCancelAPIView,
    EmployeeReimbursementListAPIView,
    EmployeeReimbursementReviewAPIView,
    EmployeeReimbursementMarkPaidAPIView,
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
    # EXPENSE
    # =====================================================
    path("create/", ExpenseCreateAPIView.as_view(), name="expense-create"),                                                                #A  perm: expense.manage
    path("list/", ExpenseListAPIView.as_view(), name="expense-list"),                                                                      #A  perm: expense.manage
    path("detail/", ExpenseDetailAPIView.as_view(), name="expense-detail"),                                                                #A  perm: expense.manage
    path("update/", ExpenseUpdateAPIView.as_view(), name="expense-update"),                                                                #A  perm: expense.manage
    path("deactivate/", ExpenseDeactivateAPIView.as_view(), name="expense-deactivate"),                                                    #A  perm: expense.manage


    # =====================================================
    # RECURRING EXPENSE
    # =====================================================
    path("recurring/create/", RecurringExpenseCreateAPIView.as_view(), name="recurring-expense-create"),                                   #A  perm: expense.manage
    path("recurring/list/", RecurringExpenseListAPIView.as_view(), name="recurring-expense-list"),                                         #A  perm: expense.manage
    path("recurring/detail/", RecurringExpenseDetailAPIView.as_view(), name="recurring-expense-detail"),                                   #A  perm: expense.manage
    path("recurring/update/", RecurringExpenseUpdateAPIView.as_view(), name="recurring-expense-update"),                                   #A  perm: expense.manage
    path("recurring/deactivate/", RecurringExpenseDeactivateAPIView.as_view(), name="recurring-expense-deactivate"),                       #A  perm: expense.manage


    # =====================================================
    # RECURRING EXPENSE ENTRY
    # =====================================================
    path("recurring/entries/create/", RecurringExpenseEntryCreateAPIView.as_view(), name="recurring-expense-entry-create"),                #A  perm: expense.manage
    path("recurring/entries/update/", RecurringExpenseEntryUpdateAPIView.as_view(), name="recurring-expense-entry-update"),                #A  perm: expense.manage
    path("recurring/entries/deactivate/", RecurringExpenseEntryDeactivateAPIView.as_view(), name="recurring-expense-entry-deactivate"),    #A  perm: expense.manage


    # =====================================================
    # EMPLOYEE REIMBURSEMENTS
    # =====================================================
    path("reimbursements/create/", EmployeeReimbursementCreateAPIView.as_view(), name="reimbursement-create"),                             #E
    path("reimbursements/my/", EmployeeReimbursementMyListAPIView.as_view(), name="reimbursement-my-list"),                                #E
    path("reimbursements/detail/", EmployeeReimbursementDetailAPIView.as_view(), name="reimbursement-detail"),                             #E #A  own, or reimbursement.review/pay
    path("reimbursements/cancel/", EmployeeReimbursementCancelAPIView.as_view(), name="reimbursement-cancel"),                             #E
    path("reimbursements/list/", EmployeeReimbursementListAPIView.as_view(), name="reimbursement-list"),                                   #A  scope: all (reimbursement.review/pay) | self
    path("reimbursements/review/", EmployeeReimbursementReviewAPIView.as_view(), name="reimbursement-review"),                             #A  perm: reimbursement.review  + not own
    path("reimbursements/mark-paid/", EmployeeReimbursementMarkPaidAPIView.as_view(), name="reimbursement-mark-paid"),                     #A  perm: reimbursement.pay  + not own
]