from __future__ import annotations

from django.contrib import admin

from .models import ScheduleItem, WeddingEvent, WeddingLocation


@admin.register(WeddingEvent)
class WeddingEventAdmin(admin.ModelAdmin):
    list_display = ("name", "wedding", "event_type", "date", "start_time", "requires_rsvp", "is_active")
    list_filter = ("event_type", "requires_rsvp", "requires_qr_code", "is_active", "date")
    search_fields = ("name", "wedding__bride_full_name", "wedding__groom_full_name")
    autocomplete_fields = ["wedding", "location"]
    ordering = ("wedding", "date", "start_time")


@admin.register(WeddingLocation)
class WeddingLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "wedding", "address", "contact_phone")
    search_fields = ("name", "address", "wedding__bride_full_name", "wedding__groom_full_name")
    autocomplete_fields = ["wedding"]


@admin.register(ScheduleItem)
class ScheduleItemAdmin(admin.ModelAdmin):
    list_display = ("title", "wedding", "date", "start_time", "display_order", "is_public")
    list_filter = ("is_public", "date")
    search_fields = ("title", "wedding__bride_full_name", "wedding__groom_full_name")
    autocomplete_fields = ["wedding", "event", "location"]
    ordering = ("wedding", "display_order")
