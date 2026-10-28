from django.urls import path

from .views import (
    VendorCreateAPIView,
    VendorListAPIView,
    VendorDetailAPIView,
    VendorUpdateAPIView,
    VendorDeactivateAPIView,
)


urlpatterns = [
    # Vendor CRUD
    path("create/", VendorCreateAPIView.as_view(), name="vendor-create"),
    path("list/", VendorListAPIView.as_view(), name="vendor-list"),
    path("detail/", VendorDetailAPIView.as_view(), name="vendor-detail"),
    path("update/", VendorUpdateAPIView.as_view(), name="vendor-update"),
    path("deactivate/", VendorDeactivateAPIView.as_view(), name="vendor-deactivate"),
]