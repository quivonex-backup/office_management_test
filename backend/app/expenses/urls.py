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
)


urlpatterns = [

    # =====================================================
    # EXPENSE
    # =====================================================
    path("create/", ExpenseCreateAPIView.as_view(), name="expense-create"),
    path("list/", ExpenseListAPIView.as_view(), name="expense-list"),
    path("detail/", ExpenseDetailAPIView.as_view(), name="expense-detail"),
    path("update/", ExpenseUpdateAPIView.as_view(), name="expense-update"),
    path("deactivate/", ExpenseDeactivateAPIView.as_view(), name="expense-deactivate"),


    # =====================================================
    # RECURRING EXPENSE
    # =====================================================
    path("recurring/create/", RecurringExpenseCreateAPIView.as_view(), name="recurring-expense-create"),
    path("recurring/list/", RecurringExpenseListAPIView.as_view(), name="recurring-expense-list"),
    path("recurring/detail/", RecurringExpenseDetailAPIView.as_view(), name="recurring-expense-detail"),
    path("recurring/update/", RecurringExpenseUpdateAPIView.as_view(), name="recurring-expense-update"),
    path("recurring/deactivate/", RecurringExpenseDeactivateAPIView.as_view(), name="recurring-expense-deactivate"),


    # =====================================================
    # RECURRING EXPENSE ENTRY
    # =====================================================
    path("recurring/entries/create/", RecurringExpenseEntryCreateAPIView.as_view(), name="recurring-expense-entry-create"),
    path("recurring/entries/update/", RecurringExpenseEntryUpdateAPIView.as_view(), name="recurring-expense-entry-update"),
    path("recurring/entries/deactivate/", RecurringExpenseEntryDeactivateAPIView.as_view(), name="recurring-expense-entry-deactivate"),
]