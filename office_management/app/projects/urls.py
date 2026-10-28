from django.urls import path
from .views import (
    ProjectCreateAPIView,
    ProjectListAPIView,
    ProjectDetailAPIView,
    ProjectUpdateAPIView,
    ProjectDeactivateAPIView,

    ProjectTeamAllocationCreateAPIView,
    ProjectTeamAllocationListAPIView,
    ProjectTeamAllocationDetailAPIView,
    ProjectTeamAllocationUpdateAPIView,
    ProjectTeamAllocationDeactivateAPIView,
    ProjectTeamAPIView,
    EmployeeProjectsAPIView,
)

urlpatterns = [
    # Project CRUD
    path("create/", ProjectCreateAPIView.as_view(), name="project-create"),
    path("list/", ProjectListAPIView.as_view(), name="project-list"),
    path("detail/", ProjectDetailAPIView.as_view(), name="project-detail"),
    path("update/", ProjectUpdateAPIView.as_view(), name="project-update"),
    path("deactivate/", ProjectDeactivateAPIView.as_view(), name="project-deactivate"),

    # Team Allocation
    path("team-allocation/create/", ProjectTeamAllocationCreateAPIView.as_view(), name="project-team-allocation-create"),
    path("team-allocation/list/", ProjectTeamAllocationListAPIView.as_view(), name="project-team-allocation-list"),
    path("team-allocation/detail/", ProjectTeamAllocationDetailAPIView.as_view(), name="project-team-allocation-detail"),
    path("team-allocation/update/", ProjectTeamAllocationUpdateAPIView.as_view(), name="project-team-allocation-update"),
    path("team-allocation/deactivate/", ProjectTeamAllocationDeactivateAPIView.as_view(), name="project-team-allocation-deactivate"),
    path("team-allocation/project-team/", ProjectTeamAPIView.as_view(), name="project-team"),
    path("team-allocation/employee-projects/", EmployeeProjectsAPIView.as_view(), name="employee-projects"),
]