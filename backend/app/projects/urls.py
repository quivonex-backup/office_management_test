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

    ProjectHeadAssignAPIView,

    MyProjectsAPIView,
    MyProjectsAsHeadAPIView,
    MyProjectDetailAPIView,

    TaskCreateAPIView,
    TaskListAPIView,
    TaskDetailAPIView,
    TaskUpdateAPIView,
    TaskStatusUpdateAPIView,
    TaskDeactivateAPIView,
    MyTasksAPIView,
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

    path("team-allocation/assign-head/", ProjectHeadAssignAPIView.as_view(), name="project-head-assign"),

    # Employee self-service
    path("my-projects/", MyProjectsAPIView.as_view(), name="project-my-projects"),
    path("my-projects-as-head/", MyProjectsAsHeadAPIView.as_view(), name="project-my-projects-as-head"),
    path("my-project-detail/", MyProjectDetailAPIView.as_view(), name="project-my-project-detail"),

    # Tasks
    path("task/create/", TaskCreateAPIView.as_view(), name="task-create"),
    path("task/list/", TaskListAPIView.as_view(), name="task-list"),
    path("task/detail/", TaskDetailAPIView.as_view(), name="task-detail"),
    path("task/update/", TaskUpdateAPIView.as_view(), name="task-update"),
    path("task/status-update/", TaskStatusUpdateAPIView.as_view(), name="task-status-update"),
    path("task/deactivate/", TaskDeactivateAPIView.as_view(), name="task-deactivate"),
    path("task/my-tasks/", MyTasksAPIView.as_view(), name="task-my-tasks"),
]