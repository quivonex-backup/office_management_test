from django.urls import path
from .views import (
    ClientCreateAPIView,
    ClientListAPIView,
    ClientDetailAPIView,
    ClientUpdateAPIView,
    ClientDeactivateAPIView,
)


urlpatterns = [
    path("create/", ClientCreateAPIView.as_view(), name="client-create"),
    path("list/", ClientListAPIView.as_view(), name="client-list"),
    path("detail/", ClientDetailAPIView.as_view(), name="client-detail"),
    path("update/", ClientUpdateAPIView.as_view(), name="client-update"),
    path("deactivate/", ClientDeactivateAPIView.as_view(), name="client-deactivate"),
]