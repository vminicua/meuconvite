from __future__ import annotations

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import MusicTrack, Wedding, WeddingGalleryPhoto, WeddingMember


@admin.register(MusicTrack)
class MusicTrackAdmin(admin.ModelAdmin):
    list_display = ("title", "artist", "is_default", "is_active", "display_order", "created_at")
    list_filter = ("is_default", "is_active", "created_at")
    search_fields = ("title", "artist")
    autocomplete_fields = ("uploaded_by",)
    ordering = ("display_order", "artist", "title")


class WeddingMemberInline(admin.TabularInline):
    model = WeddingMember
    extra = 0
    autocomplete_fields = ["user"]
    fields = ("user", "role", "is_active", "can_manage_guests", "can_check_in", "can_view_reports")


class WeddingGalleryPhotoInline(admin.TabularInline):
    model = WeddingGalleryPhoto
    extra = 0
    fields = ("image", "external_url", "caption", "display_order", "is_visible")


@admin.register(Wedding)
class WeddingAdmin(admin.ModelAdmin):
    list_display = ("display_names", "main_date", "city", "status", "owner", "created_at")
    list_filter = ("status", "main_date", "country", "created_at")
    search_fields = (
        "primary_name",
        "secondary_name",
        "slug",
        "owner__email",
        "city",
    )
    date_hierarchy = "main_date"
    readonly_fields = ("public_token", "created_at", "updated_at", "published_at")
    autocomplete_fields = ["owner"]
    inlines = [WeddingMemberInline, WeddingGalleryPhotoInline]


@admin.register(WeddingGalleryPhoto)
class WeddingGalleryPhotoAdmin(admin.ModelAdmin):
    list_display = ("wedding", "caption", "display_order", "is_visible", "created_at")
    list_filter = ("is_visible", "created_at")
    search_fields = ("wedding__primary_name", "wedding__secondary_name", "caption")
    autocomplete_fields = ["wedding"]

    fieldsets = (
        (_("Noivos"), {
            "fields": (
                "owner",
                ("primary_name", "secondary_name"),
                ("primary_short_name", "secondary_short_name"),
            )
        }),
        (_("Celebração"), {"fields": ("main_date", "city", "country", "timezone", "rsvp_deadline")}),
        (_("Endereços"), {"fields": ("slug", "public_token")}),
        (_("Conteúdo"), {"fields": ("cover_image", "cover_message", "invitation_message", "sms_invitation_message", "whatsapp_invitation_message", "welcome_message", "story", "hashtag")}),
        (_("Aspecto"), {
            "fields": (
                "selected_template",
                ("primary_color", "secondary_color"),
                "invitation_music",
                "invitation_track",
                "show_music",
                "show_countdown",
                "show_seat_before_event",
            )
        }),
        (_("Estado"), {"fields": ("status", "blocked_reason", "published_at", "created_at", "updated_at")}),
    )


@admin.register(WeddingMember)
class WeddingMemberAdmin(admin.ModelAdmin):
    list_display = ("user", "wedding", "role", "is_active", "accepted_at")
    list_filter = ("role", "is_active")
    search_fields = ("user__email", "wedding__primary_name", "wedding__secondary_name")
    autocomplete_fields = ["wedding", "user"]
