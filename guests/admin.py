from django.contrib import admin

from .models import Guest, InvitationDelivery


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "wedding", "phone", "party_size", "is_active")
    list_filter = ("is_active",)
    search_fields = ("full_name", "phone", "email")


@admin.register(InvitationDelivery)
class InvitationDeliveryAdmin(admin.ModelAdmin):
    list_display = ("guest", "channel", "status", "destination", "created_at", "sent_at")
    list_filter = ("channel", "status", "created_at")
    search_fields = ("guest__full_name", "destination", "provider_sid")
    readonly_fields = (
        "wedding", "guest", "channel", "status", "destination", "message_body",
        "provider", "provider_sid", "error_code", "error_message", "sent_by",
        "sent_at", "created_at", "updated_at",
    )
