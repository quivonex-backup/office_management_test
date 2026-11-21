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

urlpatterns = [
    # FCM
    path("device-token/register/", DeviceTokenRegisterAPIView.as_view(), name="device-token-register"),

    # Notifications
    path("notifications/list/", NotificationListAPIView.as_view(), name="notification-list"),
    path("notifications/mark-read/", NotificationMarkReadAPIView.as_view(), name="notification-mark-read"),
    path("notifications/mark-all-read/", NotificationMarkAllReadAPIView.as_view(), name="notification-mark-all-read"),
    path("notifications/unread-count/", NotificationUnreadCountAPIView.as_view(), name="notification-unread-count"),
    path("notifications/delete/", NotificationDeleteAPIView.as_view(), name="notification-delete"),

    # Announcements
    path("announcements/create/", AnnouncementCreateAPIView.as_view(), name="announcement-create"),
    path("announcements/list/", AnnouncementListAPIView.as_view(), name="announcement-list"),
    path("announcements/update/", AnnouncementUpdateAPIView.as_view(), name="announcement-update"),
    path("announcements/deactivate/", AnnouncementDeactivateAPIView.as_view(), name="announcement-deactivate"),
    path("announcements/my/", MyAnnouncementsAPIView.as_view(), name="announcement-my"),

    # Project chat
    path("project-chat/messages/", ProjectChatMessagesAPIView.as_view(), name="project-chat-messages"),
    path("project-chat/send/", ProjectChatSendAPIView.as_view(), name="project-chat-send"),
    path("project-chat/delete/", ProjectChatDeleteAPIView.as_view(), name="project-chat-delete"),
    path("project-chat/settings/", ProjectChatSettingsAPIView.as_view(), name="project-chat-settings"),

    path("test-notification/", TestSendNotificationAPIView.as_view(), name="test-notification"),
]