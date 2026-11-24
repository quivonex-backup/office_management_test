from django.contrib import admin

from .models import Ticket, TicketCategory, TicketComment


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("ticket_code", "subject", "organization", "category", "priority", "status", "created_at")
    list_filter = ("status", "priority", "organization")
    search_fields = ("ticket_code", "subject")


admin.site.register(TicketCategory)
admin.site.register(TicketComment)
