from django.contrib import admin

from .models import Gift, GiftSelection, Guest, InvitationDelivery


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "wedding", "phone", "party_size", "is_active")
    list_filter = ("is_active",)
    search_fields = ("full_name", "phone", "email")


@admin.register(InvitationDelivery)
class InvitationDeliveryAdmin(admin.ModelAdmin):
    list_display = ("guest", "channel", "status", "destination", "counts_toward_limit", "created_at", "sent_at")
    list_filter = ("channel", "status", "counts_toward_limit", "created_at")
    search_fields = ("guest__full_name", "destination", "provider_sid")
    readonly_fields = (
        "wedding", "guest", "channel", "status", "destination", "message_body",
        "provider", "provider_sid", "error_code", "error_message", "sent_by",
        "sent_at", "counts_toward_limit", "created_at", "updated_at",
    )


@admin.register(Gift)
class GiftAdmin(admin.ModelAdmin):
    list_display = ("name", "wedding", "allow_multiple", "is_active", "display_order")
    list_filter = ("allow_multiple", "is_active")
    search_fields = ("name", "wedding__primary_name", "wedding__secondary_name")


@admin.register(GiftSelection)
class GiftSelectionAdmin(admin.ModelAdmin):
    list_display = ("gift", "guest", "created_at")
    search_fields = ("gift__name", "guest__full_name")
