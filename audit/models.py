from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import UUIDModel


class AuditAction(models.TextChoices):
    """Critical actions worth keeping a permanent trail of."""

    LOGIN = "login", _("Início de sessão")
    LOGIN_FAILED = "login_failed", _("Tentativa de início de sessão falhada")
    LOGOUT = "logout", _("Fim de sessão")
    CREATE = "create", _("Criação")
    UPDATE = "update", _("Alteração")
    DELETE = "delete", _("Eliminação")
    PUBLISH = "publish", _("Publicação")
    INVITE_SENT = "invite_sent", _("Convite enviado")
    INVITE_REVOKED = "invite_revoked", _("Convite revogado")
    RSVP_SUBMITTED = "rsvp_submitted", _("Confirmação submetida")
    CHECKIN = "checkin", _("Check-in")
    CHECKIN_OVERRIDE = "checkin_override", _("Check-in com autorização especial")
    IMPORT = "import", _("Importação")
    EXPORT = "export", _("Exportação")
    MEMBER_ADDED = "member_added", _("Membro adicionado")
    MEMBER_REMOVED = "member_removed", _("Membro removido")
    PERMISSION_CHANGED = "permission_changed", _("Permissões alteradas")
    ADMIN_ACTION = "admin_action", _("Operação administrativa")


class AuditLog(UUIDModel):
    """
    Append-only record of important actions.

    Rows are never updated or deleted by the application. Payloads store
    field diffs, never passwords or tokens (see `audit.services`).
    """

    wedding = models.ForeignKey(
        "weddings.Wedding",
        verbose_name=_("casamento"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("utilizador"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    actor_label = models.CharField(
        _("identificação do autor"),
        max_length=160,
        blank=True,
        help_text=_("Guardado em texto para o registo sobreviver à remoção da conta."),
    )
    action = models.CharField(
        _("acção"), max_length=40, choices=AuditAction.choices, db_index=True
    )
    model_name = models.CharField(_("modelo"), max_length=100, blank=True)
    object_id = models.CharField(_("objecto"), max_length=64, blank=True, db_index=True)
    object_label = models.CharField(_("descrição do objecto"), max_length=200, blank=True)
    old_data = models.JSONField(_("dados anteriores"), null=True, blank=True)
    new_data = models.JSONField(_("dados novos"), null=True, blank=True)
    ip_address = models.GenericIPAddressField(_("endereço IP"), null=True, blank=True)
    user_agent = models.CharField(_("agente"), max_length=400, blank=True)
    created_at = models.DateTimeField(_("data"), auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("registo de auditoria")
        verbose_name_plural = _("registos de auditoria")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["wedding", "-created_at"], name="audit_wedding_date_idx"),
            models.Index(fields=["action", "-created_at"], name="audit_action_date_idx"),
            models.Index(fields=["model_name", "object_id"], name="audit_object_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_action_display()} — {self.actor_label or 'sistema'}"
