from django.urls import path

from .views import (
    MyVisitorListAPIView,
    VisitCheckOutAPIView,
    VisitCreateAPIView,
    VisitDeactivateAPIView,
    VisitDetailAPIView,
    VisitListAPIView,
    VisitLookupAPIView,
    VisitUpdateAPIView,
)


# ---------------------------------------------------------------------------
# Who calls what:
#   #SU  super admin (platform)        #A  organization admin side
#   #E   employee self-service         #PUB public (no token)   #DEV debug only
#   perm: <code>  enforced permission code (organization owner always passes;
#                 others need an access role that has the code)
# ---------------------------------------------------------------------------
urlpatterns = [
    path("visit/create/", VisitCreateAPIView.as_view(), name="visit-create"),                   #A  perm: visitor.manage
    path("visit/list/", VisitListAPIView.as_view(), name="visit-list"),                         #A  perm: visitor.manage
    path("visit/detail/", VisitDetailAPIView.as_view(), name="visit-detail"),                   #A  perm: visitor.manage
    path("visit/update/", VisitUpdateAPIView.as_view(), name="visit-update"),                   #A  perm: visitor.manage
    path("visit/check-out/", VisitCheckOutAPIView.as_view(), name="visit-check-out"),           #A  perm: visitor.manage
    path("visit/deactivate/", VisitDeactivateAPIView.as_view(), name="visit-deactivate"),       #A  perm: visitor.manage
    path("visit/lookup/", VisitLookupAPIView.as_view(), name="visit-lookup"),                   #A  perm: visitor.manage
    path("visit/my-visitors/", MyVisitorListAPIView.as_view(), name="visit-my-visitors"),       #E  any employee (host)
]
