from django.urls import path

from .views import (
    MyTicketListAPIView,
    TicketAssignAPIView,
    TicketCategoryCreateAPIView,
    TicketCategoryDeactivateAPIView,
    TicketCategoryListAPIView,
    TicketCategoryOptionsAPIView,
    TicketCategoryUpdateAPIView,
    TicketCommentAPIView,
    TicketCreateAPIView,
    TicketDetailAPIView,
    TicketListAPIView,
    TicketStatusUpdateAPIView,
    TicketUpdateAPIView,
)


# ---------------------------------------------------------------------------
# Who calls what:
#   #SU  super admin (platform)        #A  organization admin side
#   #E   employee self-service         #PUB public (no token)   #DEV debug only
#   perm: <code>  enforced permission code (organization owner always passes;
#                 others need an access role that has the code)
#   handler = ticket.handle + same department as the category, or the assignee
# ---------------------------------------------------------------------------
urlpatterns = [
    # Categories
    path("category/create/", TicketCategoryCreateAPIView.as_view(), name="helpdesk-category-create"),              #A     perm: ticket.manage
    path("category/list/", TicketCategoryListAPIView.as_view(), name="helpdesk-category-list"),                    #A     perm: ticket.manage, ticket.handle (any)
    path("category/update/", TicketCategoryUpdateAPIView.as_view(), name="helpdesk-category-update"),              #A     perm: ticket.manage
    path("category/deactivate/", TicketCategoryDeactivateAPIView.as_view(), name="helpdesk-category-deactivate"),  #A     perm: ticket.manage
    path("category/options/", TicketCategoryOptionsAPIView.as_view(), name="helpdesk-category-options"),           #E     any employee

    # Tickets
    path("ticket/create/", TicketCreateAPIView.as_view(), name="helpdesk-ticket-create"),                          #E #A  any employee (raised_by_id: ticket.manage)
    path("ticket/my-tickets/", MyTicketListAPIView.as_view(), name="helpdesk-ticket-my-tickets"),                  #E     any employee
    path("ticket/list/", TicketListAPIView.as_view(), name="helpdesk-ticket-list"),                                #A     perm: ticket.manage (all), ticket.handle (own department + assigned)
    path("ticket/detail/", TicketDetailAPIView.as_view(), name="helpdesk-ticket-detail"),                          #E #A  raiser | handler | perm: ticket.manage
    path("ticket/assign/", TicketAssignAPIView.as_view(), name="helpdesk-ticket-assign"),                          #A     handler | perm: ticket.manage
    path("ticket/update/", TicketUpdateAPIView.as_view(), name="helpdesk-ticket-update"),                          #A     handler | perm: ticket.manage
    path("ticket/status-update/", TicketStatusUpdateAPIView.as_view(), name="helpdesk-ticket-status-update"),      #E #A  raiser | handler | perm: ticket.manage
    path("ticket/comment/", TicketCommentAPIView.as_view(), name="helpdesk-ticket-comment"),                       #E #A  raiser | handler | perm: ticket.manage
]
