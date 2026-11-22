from django.urls import path

from .views import (
    DeviceTokenRegisterAPIView,

    NotificationListAPIView,
    NotificationMarkReadAPIView,
    NotificationMarkAllReadAPIView,
    NotificationUnreadCountAPIView,
    NotificationDeleteAPIView,

    AnnouncementCreateAPIView,
    AnnouncementListAPIView,
    AnnouncementUpdateAPIView,
    AnnouncementDeactivateAPIView,
    MyAnnouncementsAPIView,

    ProjectChatMessagesAPIView,
    ProjectChatSendAPIView,
    ProjectChatDeleteAPIView,
    ProjectChatSettingsAPIView,

    TestSendNotificationAPIView,
)

# ---------------------------------------------------------------------------
# Who calls what:
#   #SU  super admin (platform)        #A  organization admin side
#   #E   employee self-service         #PUB public (no token)   #DEV debug only
#   perm: <code>  enforced permission code (organization owner always passes;
#                 others need an access role that has the code)
# ---------------------------------------------------------------------------
urlpatterns = [
    # FCM
    path("device-token/register/", DeviceTokenRegisterAPIView.as_view(), name="device-token-register"),        #E #A

    # Notifications
    path("notifications/list/", NotificationListAPIView.as_view(), name="notification-list"),                  #E #A
    path("notifications/mark-read/", NotificationMarkReadAPIView.as_view(), name="notification-mark-read"),    #E #A
    path("notifications/mark-all-read/", NotificationMarkAllReadAPIView.as_view(), name="notification-mark-all-read"),#E #A
    path("notifications/unread-count/", NotificationUnreadCountAPIView.as_view(), name="notification-unread-count"),#E #A
    path("notifications/delete/", NotificationDeleteAPIView.as_view(), name="notification-delete"),            #E #A

    # Announcements
    path("announcements/create/", AnnouncementCreateAPIView.as_view(), name="announcement-create"),            #A
    path("announcements/list/", AnnouncementListAPIView.as_view(), name="announcement-list"),                  #A
    path("announcements/update/", AnnouncementUpdateAPIView.as_view(), name="announcement-update"),            #A
    path("announcements/deactivate/", AnnouncementDeactivateAPIView.as_view(), name="announcement-deactivate"),#A
    path("announcements/my/", MyAnnouncementsAPIView.as_view(), name="announcement-my"),                       #E #A

    # Project chat
    path("project-chat/messages/", ProjectChatMessagesAPIView.as_view(), name="project-chat-messages"),        #E #A
    path("project-chat/send/", ProjectChatSendAPIView.as_view(), name="project-chat-send"),                    #E #A
    path("project-chat/delete/", ProjectChatDeleteAPIView.as_view(), name="project-chat-delete"),              #E #A
    path("project-chat/settings/", ProjectChatSettingsAPIView.as_view(), name="project-chat-settings"),        #A

    path("test-notification/", TestSendNotificationAPIView.as_view(), name="test-notification"),               #DEV  only when DEBUG=True
]