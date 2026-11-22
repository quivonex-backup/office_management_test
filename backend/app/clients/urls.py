from django.urls import path
from .views import (
    ClientCreateAPIView,
    ClientListAPIView,
    ClientDetailAPIView,
    ClientUpdateAPIView,
    ClientDeactivateAPIView,
)


# ---------------------------------------------------------------------------
# Who calls what:
#   #SU  super admin (platform)        #A  organization admin side
#   #E   employee self-service         #PUB public (no token)   #DEV debug only
#   perm: <code>  enforced permission code (organization owner always passes;
#                 others need an access role that has the code)
# ---------------------------------------------------------------------------
urlpatterns = [
    path("create/", ClientCreateAPIView.as_view(), name="client-create"),                #A
    path("list/", ClientListAPIView.as_view(), name="client-list"),                      #A
    path("detail/", ClientDetailAPIView.as_view(), name="client-detail"),                #A
    path("update/", ClientUpdateAPIView.as_view(), name="client-update"),                #A
    path("deactivate/", ClientDeactivateAPIView.as_view(), name="client-deactivate"),    #A
]