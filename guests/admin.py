from django.contrib import admin

from .models import Guest


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "wedding", "phone", "party_size", "is_active")
    list_filter = ("is_active",)
    search_fields = ("full_name", "phone", "email")
