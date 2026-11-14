from django.urls import path
from .views import (
    StateCreateAPIView, StateDeactivateAPIView, StateListAPIView,
    DistrictCreateAPIView, DistrictDeactivateAPIView, DistrictListAPIView,
    TalukaCreateAPIView, TalukaDeactivateAPIView, TalukaListAPIView,
)

urlpatterns = [
    # State
    path('states/create/', StateCreateAPIView.as_view(), name='state-create'),
    path('states/deactivate/', StateDeactivateAPIView.as_view(), name='state-deactivate'),
    path('states/list/', StateListAPIView.as_view(), name='state-list'),

    # District
    path('districts/create/', DistrictCreateAPIView.as_view(), name='district-create'),
    path('districts/deactivate/', DistrictDeactivateAPIView.as_view(), name='district-deactivate'),
    path('districts/list/', DistrictListAPIView.as_view(), name='district-list'),

    # Taluka
    path('talukas/create/', TalukaCreateAPIView.as_view(), name='taluka-create'),
    path('talukas/deactivate/', TalukaDeactivateAPIView.as_view(), name='taluka-deactivate'),
    path('talukas/list/', TalukaListAPIView.as_view(), name='taluka-list'),
]