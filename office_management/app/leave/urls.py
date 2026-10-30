# =========================================================
# FILE: urls.py
# =========================================================
from django.urls import path

from .views import (
    LeaveTypeListAPIView,
    LeaveTypeCreateAPIView,
    LeaveTypeUpdateAPIView,
    LeaveTypeDeactivateAPIView,

    MyLeaveBalanceListAPIView,
    OrganizationLeaveBalanceListAPIView,
    LeaveBalanceInitializeAPIView,
    LeaveBalanceAdjustAPIView,

    LeaveApplicationCreateAPIView,
    MyLeaveApplicationListAPIView,
    OrganizationLeaveApplicationListAPIView,
    LeaveApplicationReviewAPIView,
    MyLeaveApplicationCancelAPIView,
    OrganizationLeaveApplicationCancelAPIView,

    OrganizationLeaveTransactionListAPIView,
)


urlpatterns = [

    # Leave Types
    path("types/list/", LeaveTypeListAPIView.as_view()),
    path("types/create/", LeaveTypeCreateAPIView.as_view()),
    path("types/update/", LeaveTypeUpdateAPIView.as_view()),
    path("types/deactivate/", LeaveTypeDeactivateAPIView.as_view()),

    # Leave Balances
    path("balances/my/", MyLeaveBalanceListAPIView.as_view()),
    path("balances/list/", OrganizationLeaveBalanceListAPIView.as_view()),
    path("balances/initialize/", LeaveBalanceInitializeAPIView.as_view()),
    path("balances/adjust/", LeaveBalanceAdjustAPIView.as_view()),

    # Leave Applications
    path("applications/create/", LeaveApplicationCreateAPIView.as_view()),
    path("applications/my/", MyLeaveApplicationListAPIView.as_view()),
    path("applications/list/", OrganizationLeaveApplicationListAPIView.as_view()),
    path("applications/review/", LeaveApplicationReviewAPIView.as_view()),
    path("applications/cancel/my/", MyLeaveApplicationCancelAPIView.as_view()),
    path("applications/cancel/organization/", OrganizationLeaveApplicationCancelAPIView.as_view()),

    # Leave Transactions
    path("transactions/list/", OrganizationLeaveTransactionListAPIView.as_view()),
]