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

# ---------------------------------------------------------------------------
# Who calls what:
#   #SU  super admin (platform)        #A  organization admin side
#   #E   employee self-service         #PUB public (no token)   #DEV debug only
#   perm: <code>  enforced permission code (organization owner always passes;
#                 others need an access role that has the code)
# ---------------------------------------------------------------------------
urlpatterns = [
    # META OAUTH
    path("meta/connect/", MetaConnectAPIView.as_view(), name="meta-connect"),                                    #A
    path("meta/callback/", MetaCallbackAPIView.as_view(), name="meta-callback"),                                 #PUB  Meta OAuth redirect

    # SOCIAL ACCOUNTS
    path("accounts/list/", SocialAccountListAPIView.as_view(), name="social-account-list"),                      #A
    path("accounts/activate/", SocialAccountActivateAPIView.as_view(), name="social-account-activate"),          #A
    path("accounts/deactivate/", SocialAccountDeactivateAPIView.as_view(), name="social-account-deactivate"),    #A
    path("accounts/delete/", SocialAccountDeleteAPIView.as_view(), name="social-account-delete"),                #A
    path("accounts/media/list/",SocialAccountMediaListAPIView.as_view(),name="social-account-media-list"),       #A

    # SOCIAL POSTS
    path("posts/create/", SocialPostCreateAPIView.as_view(), name="social-post-create"),                         #A
    path("posts/list/", SocialPostListAPIView.as_view(), name="social-post-list"),                               #A
    path("posts/detail/", SocialPostDetailAPIView.as_view(), name="social-post-detail"),                         #A
    path("posts/update/", SocialPostUpdateAPIView.as_view(), name="social-post-update"),                         #A
    path("posts/delete/", SocialPostDeleteAPIView.as_view(), name="social-post-delete"),                         #A
    path("posts/publish/", SocialPostPublishAPIView.as_view(), name="social-post-publish"),                      #A
    path("posts/schedule/", SocialPostScheduleAPIView.as_view(), name="social-post-schedule"),                   #A
    path("posts/unschedule/", SocialPostUnscheduleAPIView.as_view(), name="social-post-unschedule"),             #A

    # PUBLICATIONS
    path("publications/list/", SocialPublicationListAPIView.as_view(), name="social-publication-list"),          #A
    path("publications/detail/", SocialPublicationDetailAPIView.as_view(), name="social-publication-detail"),    #A
]