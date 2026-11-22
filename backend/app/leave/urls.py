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


# ---------------------------------------------------------------------------
# Who calls what:
#   #SU  super admin (platform)        #A  organization admin side
#   #E   employee self-service         #PUB public (no token)   #DEV debug only
#   perm: <code>  enforced permission code (organization owner always passes;
#                 others need an access role that has the code)
# ---------------------------------------------------------------------------
urlpatterns = [

    # Leave Types
    path("types/list/", LeaveTypeListAPIView.as_view()),                                               #E #A
    path("types/create/", LeaveTypeCreateAPIView.as_view()),                                           #A  perm: settings.manage
    path("types/update/", LeaveTypeUpdateAPIView.as_view()),                                           #A  perm: settings.manage
    path("types/deactivate/", LeaveTypeDeactivateAPIView.as_view()),                                   #A  perm: settings.manage

    # Leave Balances
    path("balances/my/", MyLeaveBalanceListAPIView.as_view()),                                         #E
    path("balances/list/", OrganizationLeaveBalanceListAPIView.as_view()),                             #A  scope: self|team|all (leave.view_*)
    path("balances/initialize/", LeaveBalanceInitializeAPIView.as_view()),                             #A  perm: settings.manage
    path("balances/adjust/", LeaveBalanceAdjustAPIView.as_view()),                                     #A  perm: settings.manage

    # Leave Applications
    path("applications/create/", LeaveApplicationCreateAPIView.as_view()),                             #E
    path("applications/my/", MyLeaveApplicationListAPIView.as_view()),                                 #E
    path("applications/list/", OrganizationLeaveApplicationListAPIView.as_view()),                     #A  scope: self|team|all (leave.view_*)
    path("applications/review/", LeaveApplicationReviewAPIView.as_view()),                             #A  perm: leave.approve  + in caller's scope, not own
    path("applications/cancel/my/", MyLeaveApplicationCancelAPIView.as_view()),                        #E
    path("applications/cancel/organization/", OrganizationLeaveApplicationCancelAPIView.as_view()),    #A  perm: leave.approve  + in caller's scope, not own

    # Leave Transactions
    path("transactions/list/", OrganizationLeaveTransactionListAPIView.as_view()),                     #A  perm: leave.view_all, settings.manage (any)
]