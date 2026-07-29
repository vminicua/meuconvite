from __future__ import annotations

from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only: the audit trail must not be editable from the admin."""

    list_display = ("created_at", "action", "actor_label", "model_name", "object_label")
    list_filter = ("action", "created_at")
    search_fields = ("actor_label", "object_id", "object_label", "model_name")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_select_related = ("user", "wedding")

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
