from django.contrib import admin

from .models import Visit


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ("visit_code", "visitor_name", "visitor_mobile", "organization", "purpose", "check_in_at", "check_out_at")
    list_filter = ("purpose", "organization")
    search_fields = ("visit_code", "visitor_name", "visitor_mobile", "visitor_company")
