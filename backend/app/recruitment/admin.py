from django.contrib import admin

from .models import Applicant, ApplicantCheck, ApplicantDocument, ApplicantInterview, ApplicantOffer, ApplicantStatusHistory


@admin.register(Applicant)
class ApplicantAdmin(admin.ModelAdmin):
    list_display = ("applicant_code", "first_name", "last_name", "organization", "stage", "status", "applied_on")
    list_filter = ("stage", "status", "organization")
    search_fields = ("applicant_code", "first_name", "last_name", "email", "mobile")


admin.site.register(ApplicantDocument)
admin.site.register(ApplicantInterview)
admin.site.register(ApplicantOffer)
admin.site.register(ApplicantCheck)
admin.site.register(ApplicantStatusHistory)
