from django.urls import path

from .views import (
    ApplicantCreateAPIView,
    ApplicantListAPIView,
    ApplicantDetailAPIView,
    ApplicantUpdateAPIView,
    ApplicantStatusUpdateAPIView,
    ApplicantVerificationAPIView,
    ApplicantOnboardingAPIView,
    ApplicantConvertAPIView,
    ApplicantOfferLetterDownloadAPIView,
    OfferResponsePublicView,
    OfferLetterPublicPDFView,
)

# ---------------------------------------------------------------------------
# Who calls what:
#   #SU  super admin (platform)        #A  organization admin side
#   #E   employee self-service         #PUB public (no token)   #DEV debug only
#   perm: <code>  enforced permission code (organization owner always passes;
#                 others need an access role that has the code)
# ---------------------------------------------------------------------------
urlpatterns = [
    path("applicant/create/", ApplicantCreateAPIView.as_view(), name="applicant-create"),                                               #A  perm: applicant.create
    path("applicant/list/", ApplicantListAPIView.as_view(), name="applicant-list"),                                                     #A  perm: applicant.view  (view-only users: assigned / interviewer)
    path("applicant/detail/", ApplicantDetailAPIView.as_view(), name="applicant-detail"),                                               #A  perm: applicant.view
    path("applicant/update/", ApplicantUpdateAPIView.as_view(), name="applicant-update"),                                               #A  perm: applicant.update (applicant.view: own interview feedback only)
    path("applicant/status-update/", ApplicantStatusUpdateAPIView.as_view(), name="applicant-status-update"),                           #A  perm: applicant.status_update
    path("applicant/verification/", ApplicantVerificationAPIView.as_view(), name="applicant-verification"),                             #A  perm: verification.update
    path("applicant/onboarding/", ApplicantOnboardingAPIView.as_view(), name="applicant-onboarding"),                                   #A  perm: onboarding.complete (access_role_id needs access.manage)
    path("applicant/convert/", ApplicantConvertAPIView.as_view(), name="applicant-convert"),                                            #A  perm: onboarding.complete (+ employee.create_user for the login)
    path("applicant/offer-letter/download/", ApplicantOfferLetterDownloadAPIView.as_view(), name="applicant-offer-letter-download"),    #A  perm: verification.update, onboarding.complete (any)  returns PDF

    # Candidate pages (browser, no login; the token in the emailed link is the key)
    path("offer/<str:token>/", OfferResponsePublicView.as_view(), name="offer-response"),                                               #PUB  GET page / POST accept or decline (final)
    path("offer/<str:token>/letter/", OfferLetterPublicPDFView.as_view(), name="offer-letter-public"),                                  #PUB  GET offer letter PDF
]
