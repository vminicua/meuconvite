from __future__ import annotations

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import EventCategory, ScheduleItem, WeddingEvent, WeddingLocation


@admin.register(EventCategory)
class EventCategoryAdmin(admin.ModelAdmin):
    """
    Tipos de evento suportados pela plataforma.

    É aqui que a equipa MeuConvite define um tipo novo: como se chamam os
    protagonistas, que campos próprios pedir, que momentos criar e que
    programa sugerir. Não é preciso alterar código.
    """

    list_display = ("name", "code", "uses_two_names", "field_count", "is_active", "display_order")
    list_filter = ("is_active", "uses_two_names")
    search_fields = ("name", "code", "description")
    ordering = ("display_order", "name")
    list_editable = ("display_order", "is_active")
    prepopulated_fields = {"code": ("name",)}

    fieldsets = (
        (None, {"fields": ("name", "code", "description", "icon", "display_order", "is_active")}),
        (
            _("Protagonistas"),
            {
                "fields": ("uses_two_names", "primary_label", "secondary_label", "names_separator"),
                "description": _(
                    "Um casamento tem dois nomes (noiva e noivo); um aniversário tem um."
                ),
            },
        ),
        (
            _("Campos próprios"),
            {
                "fields": ("field_schema",),
                "description": _(
                    "Campos extra pedidos ao criar este tipo de evento. Exemplo: "
                    '[{"key": "idade", "label": "Idade a celebrar", "type": "number"}]'
                ),
            },
        ),
        (
            _("Sugestões automáticas"),
            {
                "fields": ("default_moments", "default_schedule", "invitation_greeting"),
                "description": _(
                    "Momentos e programa criados automaticamente quando alguém escolhe "
                    "este tipo de evento."
                ),
            },
        ),
    )

    @admin.display(description=_("campos próprios"))
    def field_count(self, obj: EventCategory) -> int:
        return len(obj.extra_fields)


@admin.register(WeddingEvent)
class WeddingEventAdmin(admin.ModelAdmin):
    list_display = ("name", "wedding", "event_type", "date", "start_time", "requires_rsvp", "is_active")
    list_filter = ("event_type", "requires_rsvp", "requires_qr_code", "is_active", "date")
    search_fields = ("name", "wedding__primary_name", "wedding__secondary_name")
    autocomplete_fields = ["wedding", "location"]
    ordering = ("wedding", "date", "start_time")


@admin.register(WeddingLocation)
class WeddingLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "wedding", "address", "contact_phone")
    search_fields = ("name", "address", "wedding__primary_name", "wedding__secondary_name")
    autocomplete_fields = ["wedding"]


@admin.register(ScheduleItem)
class ScheduleItemAdmin(admin.ModelAdmin):
    list_display = ("title", "wedding", "date", "start_time", "display_order", "is_public")
    list_filter = ("is_public", "date")
    search_fields = ("title", "wedding__primary_name", "wedding__secondary_name")
    autocomplete_fields = ["wedding", "event", "location"]
    ordering = ("wedding", "display_order")
