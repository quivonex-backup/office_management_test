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

# ---------------------------------------------------------------------------
# Who calls what:
#   #SU  super admin (platform)        #A  organization admin side
#   #E   employee self-service         #PUB public (no token)   #DEV debug only
#   perm: <code>  enforced permission code (organization owner always passes;
#                 others need an access role that has the code)
# ---------------------------------------------------------------------------
urlpatterns = [
    # =====================================================
    # PROJECT PAYMENT
    # =====================================================
    path("project/payment-create/", ProjectPaymentCreateAPIView.as_view(), name="project-payment-create"),                               #A  perm: payment.manage
    path("project/payment-list/", ProjectPaymentListAPIView.as_view(), name="project-payment-list"),                                     #A  perm: payment.manage
    path("project/payment-detail/", ProjectPaymentDetailAPIView.as_view(), name="project-payment-detail"),                               #A  perm: payment.manage
    path("project/payment-update/", ProjectPaymentUpdateAPIView.as_view(), name="project-payment-update"),                               #A  perm: payment.manage
    path("project/payment-cancel/", ProjectPaymentDeactivateAPIView.as_view(), name="project-payment-cancel"),                           #A  perm: payment.manage

    # =====================================================
    # PAYMENT TRANSACTION
    # =====================================================
    path("project/transaction/create/", ProjectPaymentTransactionCreateAPIView.as_view(), name="project-payment-transaction-create"),    #A  perm: payment.manage
    path("project/transaction/update/", ProjectPaymentTransactionUpdateAPIView.as_view(), name="project-payment-transaction-update"),    #A  perm: payment.manage

    # =====================================================
    # PROJECT PAYMENTS + TRANSACTIONS
    # =====================================================
    path("project/payments-details-by-project/", ProjectPaymentsByProjectAPIView.as_view(), name="project-payments-by-project"),         #A  perm: payment.manage

    # -----------------------------------------------------
    # PROJECT PAYMENT REMINDER
    # -----------------------------------------------------
    path("payment-reminder/", ProjectPaymentReminderAPIView.as_view(), name="project-payment-reminder"),                                 #A  perm: payment.manage

    path("project-invoice/pdf-download/", ProjectInvoicePDFAPIView.as_view(), name="project-invoice"),                                   #A  perm: payment.manage

]