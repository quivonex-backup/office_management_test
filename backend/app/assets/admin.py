from django.contrib import admin

from .models import Asset, AssetAssignment, AssetCategory


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("asset_code", "name", "organization", "category", "status", "current_holder")
    list_filter = ("status", "organization")
    search_fields = ("asset_code", "name", "serial_number")


admin.site.register(AssetCategory)
admin.site.register(AssetAssignment)
