from django.urls import path

from .views import (
    VendorCreateAPIView,
    VendorListAPIView,
    VendorDetailAPIView,
    VendorUpdateAPIView,
    VendorDeactivateAPIView,
)


# ---------------------------------------------------------------------------
# Who calls what:
#   #SU  super admin (platform)        #A  organization admin side
#   #E   employee self-service         #PUB public (no token)   #DEV debug only
#   perm: <code>  enforced permission code (organization owner always passes;
#                 others need an access role that has the code)
# ---------------------------------------------------------------------------
urlpatterns = [
    # Vendor CRUD
    path("create/", VendorCreateAPIView.as_view(), name="vendor-create"),                #A
    path("list/", VendorListAPIView.as_view(), name="vendor-list"),                      #A
    path("detail/", VendorDetailAPIView.as_view(), name="vendor-detail"),                #A
    path("update/", VendorUpdateAPIView.as_view(), name="vendor-update"),                #A
    path("deactivate/", VendorDeactivateAPIView.as_view(), name="vendor-deactivate"),    #A
]