from django.urls import path

from .views import (
    MetaConnectAPIView,
    MetaCallbackAPIView,
    SocialAccountListAPIView,
    SocialAccountActivateAPIView,
    SocialAccountDeactivateAPIView,
    SocialAccountDeleteAPIView,
    SocialAccountMediaListAPIView,
    SocialPostCreateAPIView,
    SocialPostListAPIView,
    SocialPostDetailAPIView,
    SocialPostUpdateAPIView,
    SocialPostDeleteAPIView,
    SocialPostPublishAPIView,
    SocialPostScheduleAPIView,
    SocialPostUnscheduleAPIView,
    SocialPublicationListAPIView,
    SocialPublicationDetailAPIView,
)

urlpatterns = [
    # META OAUTH
    path("meta/connect/", MetaConnectAPIView.as_view(), name="meta-connect"),
    path("meta/callback/", MetaCallbackAPIView.as_view(), name="meta-callback"),

    # SOCIAL ACCOUNTS
    path("accounts/list/", SocialAccountListAPIView.as_view(), name="social-account-list"),
    path("accounts/activate/", SocialAccountActivateAPIView.as_view(), name="social-account-activate"),
    path("accounts/deactivate/", SocialAccountDeactivateAPIView.as_view(), name="social-account-deactivate"),
    path("accounts/delete/", SocialAccountDeleteAPIView.as_view(), name="social-account-delete"),
    path("accounts/media/list/",SocialAccountMediaListAPIView.as_view(),name="social-account-media-list"),

    # SOCIAL POSTS
    path("posts/create/", SocialPostCreateAPIView.as_view(), name="social-post-create"),
    path("posts/list/", SocialPostListAPIView.as_view(), name="social-post-list"),
    path("posts/detail/", SocialPostDetailAPIView.as_view(), name="social-post-detail"),
    path("posts/update/", SocialPostUpdateAPIView.as_view(), name="social-post-update"),
    path("posts/delete/", SocialPostDeleteAPIView.as_view(), name="social-post-delete"),
    path("posts/publish/", SocialPostPublishAPIView.as_view(), name="social-post-publish"),
    path("posts/schedule/", SocialPostScheduleAPIView.as_view(), name="social-post-schedule"),
    path("posts/unschedule/", SocialPostUnscheduleAPIView.as_view(), name="social-post-unschedule"),

    # PUBLICATIONS
    path("publications/list/", SocialPublicationListAPIView.as_view(), name="social-publication-list"),
    path("publications/detail/", SocialPublicationDetailAPIView.as_view(), name="social-publication-detail"),
]