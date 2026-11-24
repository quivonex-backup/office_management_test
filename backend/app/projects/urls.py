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

# ---------------------------------------------------------------------------
# Who calls what:
#   #SU  super admin (platform)        #A  organization admin side
#   #E   employee self-service         #PUB public (no token)   #DEV debug only
#   perm: <code>  enforced permission code (organization owner always passes;
#                 others need an access role that has the code)
# ---------------------------------------------------------------------------
urlpatterns = [
    # Project CRUD
    path("create/", ProjectCreateAPIView.as_view(), name="project-create"),                                                              #A  perm: project.manage
    path("list/", ProjectListAPIView.as_view(), name="project-list"),                                                                    #A  perm: project.manage, payment.manage (any)
    path("detail/", ProjectDetailAPIView.as_view(), name="project-detail"),                                                              #A  perm: project.manage, payment.manage (any)
    path("update/", ProjectUpdateAPIView.as_view(), name="project-update"),                                                              #A  perm: project.manage
    path("deactivate/", ProjectDeactivateAPIView.as_view(), name="project-deactivate"),                                                  #A  perm: project.manage

    # Team Allocation
    path("team-allocation/create/", ProjectTeamAllocationCreateAPIView.as_view(), name="project-team-allocation-create"),                #A  perm: project.manage
    path("team-allocation/list/", ProjectTeamAllocationListAPIView.as_view(), name="project-team-allocation-list"),                      #A  perm: project.manage
    path("team-allocation/detail/", ProjectTeamAllocationDetailAPIView.as_view(), name="project-team-allocation-detail"),                #A  perm: project.manage
    path("team-allocation/update/", ProjectTeamAllocationUpdateAPIView.as_view(), name="project-team-allocation-update"),                #A  perm: project.manage
    path("team-allocation/deactivate/", ProjectTeamAllocationDeactivateAPIView.as_view(), name="project-team-allocation-deactivate"),    #A  perm: project.manage
    path("team-allocation/project-team/", ProjectTeamAPIView.as_view(), name="project-team"),                                            #A  perm: project.manage
    path("team-allocation/employee-projects/", EmployeeProjectsAPIView.as_view(), name="employee-projects"),                             #A  perm: project.manage

    path("team-allocation/assign-head/", ProjectHeadAssignAPIView.as_view(), name="project-head-assign"),                                #A  perm: project.manage

    # Employee self-service
    path("my-projects/", MyProjectsAPIView.as_view(), name="project-my-projects"),                                                       #E
    path("my-projects-as-head/", MyProjectsAsHeadAPIView.as_view(), name="project-my-projects-as-head"),                                 #E
    path("my-project-detail/", MyProjectDetailAPIView.as_view(), name="project-my-project-detail"),                                      #E

    # Tasks
    path("task/create/", TaskCreateAPIView.as_view(), name="task-create"),                                                               #E #A  perm: project.manage | project head
    path("task/list/", TaskListAPIView.as_view(), name="task-list"),                                                                     #E #A  perm: project.manage | project head
    path("task/detail/", TaskDetailAPIView.as_view(), name="task-detail"),                                                               #E #A  perm: project.manage | project head | assignee
    path("task/update/", TaskUpdateAPIView.as_view(), name="task-update"),                                                               #E #A  perm: project.manage | project head
    path("task/status-update/", TaskStatusUpdateAPIView.as_view(), name="task-status-update"),                                           #E #A  perm: project.manage | project head | assignee
    path("task/deactivate/", TaskDeactivateAPIView.as_view(), name="task-deactivate"),                                                   #E #A  perm: project.manage | project head
    path("task/my-tasks/", MyTasksAPIView.as_view(), name="task-my-tasks"),                                                              #E
]