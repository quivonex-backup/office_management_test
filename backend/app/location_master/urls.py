from django.urls import path
from .views import (
    StateCreateAPIView, StateDeactivateAPIView, StateListAPIView,
    DistrictCreateAPIView, DistrictDeactivateAPIView, DistrictListAPIView,
    TalukaCreateAPIView, TalukaDeactivateAPIView, TalukaListAPIView,
)

# ---------------------------------------------------------------------------
# Who calls what:
#   #SU  super admin (platform)        #A  organization admin side
#   #E   employee self-service         #PUB public (no token)   #DEV debug only
#   perm: <code>  enforced permission code (organization owner always passes;
#                 others need an access role that has the code)
# ---------------------------------------------------------------------------
urlpatterns = [
    # State
    path('states/create/', StateCreateAPIView.as_view(), name='state-create'),                         #SU  perm: super admin only
    path('states/deactivate/', StateDeactivateAPIView.as_view(), name='state-deactivate'),             #SU  perm: super admin only
    path('states/list/', StateListAPIView.as_view(), name='state-list'),                               #E #A #SU

    # District
    path('districts/create/', DistrictCreateAPIView.as_view(), name='district-create'),                #SU  perm: super admin only
    path('districts/deactivate/', DistrictDeactivateAPIView.as_view(), name='district-deactivate'),    #SU  perm: super admin only
    path('districts/list/', DistrictListAPIView.as_view(), name='district-list'),                      #E #A #SU

    # Taluka
    path('talukas/create/', TalukaCreateAPIView.as_view(), name='taluka-create'),                      #SU  perm: super admin only
    path('talukas/deactivate/', TalukaDeactivateAPIView.as_view(), name='taluka-deactivate'),          #SU  perm: super admin only
    path('talukas/list/', TalukaListAPIView.as_view(), name='taluka-list'),                            #E #A #SU
]