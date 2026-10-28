from django.urls import path
from .views import (
    ProjectPaymentCreateAPIView,
    ProjectPaymentListAPIView,
    ProjectPaymentDetailAPIView,
    ProjectPaymentUpdateAPIView,
    ProjectPaymentTransactionCreateAPIView,
    ProjectPaymentTransactionUpdateAPIView,
    ProjectPaymentDeactivateAPIView,
    ProjectPaymentsByProjectAPIView,
    ProjectPaymentReminderAPIView,
    ProjectInvoicePDFAPIView,
)

urlpatterns = [
    # =====================================================
    # PROJECT PAYMENT
    # =====================================================
    path("project/payment-create/", ProjectPaymentCreateAPIView.as_view(), name="project-payment-create"),
    path("project/payment-list/", ProjectPaymentListAPIView.as_view(), name="project-payment-list"),
    path("project/payment-detail/", ProjectPaymentDetailAPIView.as_view(), name="project-payment-detail"),
    path("project/payment-update/", ProjectPaymentUpdateAPIView.as_view(), name="project-payment-update"),
    path("project/payment-cancel/", ProjectPaymentDeactivateAPIView.as_view(), name="project-payment-cancel"),

    # =====================================================
    # PAYMENT TRANSACTION
    # =====================================================
    path("project/transaction/create/", ProjectPaymentTransactionCreateAPIView.as_view(), name="project-payment-transaction-create"),
    path("project/transaction/update/", ProjectPaymentTransactionUpdateAPIView.as_view(), name="project-payment-transaction-update"),

    # =====================================================
    # PROJECT PAYMENTS + TRANSACTIONS
    # =====================================================
    path("project/payments-details-by-project/", ProjectPaymentsByProjectAPIView.as_view(), name="project-payments-by-project"),

    # -----------------------------------------------------
    # PROJECT PAYMENT REMINDER
    # -----------------------------------------------------
    path("payment-reminder/", ProjectPaymentReminderAPIView.as_view(), name="project-payment-reminder"),

    path("project-invoice/pdf-download/", ProjectInvoicePDFAPIView.as_view(), name="project-invoice"),

]