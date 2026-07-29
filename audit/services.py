"""
Audit trail service.

`log_action` is intentionally forgiving: a failure writing the trail must
never break the user facing operation, but it is always reported to the
`meuconvite.audit` logger so problems are visible.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import models

from core.middleware import get_current_request
from core.utils import get_client_ip, get_user_agent, mask_email

from .models import AuditAction, AuditLog

logger = logging.getLogger("meuconvite.audit")

# Never copied into the audit payload.
SENSITIVE_FIELDS = {
    "password",
    "password1",
    "password2",
    "token",
    "public_token",
    "qr_token",
    "secret",
    "api_key",
    "csrfmiddlewaretoken",
    "session_key",
}


def _serialise_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, models.Model):
        return str(value.pk)
    return str(value)


def sanitise(data: dict | None) -> dict | None:
    """Drop sensitive keys and make the payload JSON serialisable."""
    if not data:
        return None
    clean: dict[str, Any] = {}
    for key, value in data.items():
        lowered = str(key).lower()
        if any(marker in lowered for marker in SENSITIVE_FIELDS):
            clean[key] = "***"
        elif "email" in lowered and isinstance(value, str):
            clean[key] = mask_email(value)
        else:
            clean[key] = _serialise_value(value)
    return clean


def model_to_dict(instance, fields: list[str] | None = None) -> dict:
    """Snapshot of a model instance suitable for the audit payload."""
    if instance is None:
        return {}
    data = {}
    for field in instance._meta.fields:
        if fields and field.name not in fields:
            continue
        if field.name in SENSITIVE_FIELDS:
            continue
        data[field.name] = _serialise_value(getattr(instance, field.attname, None))
    return sanitise(data) or {}


def log_action(
    *,
    action: str,
    actor=None,
    wedding=None,
    request=None,
    instance=None,
    model_name: str = "",
    object_id: str = "",
    object_label: str = "",
    old_data: dict | None = None,
    new_data: dict | None = None,
) -> AuditLog | None:
    """Write one audit record. Returns None when the write failed."""
    request = request or get_current_request()

    if instance is not None:
        model_name = model_name or f"{instance._meta.app_label}.{instance._meta.object_name}"
        object_id = object_id or str(instance.pk)
        object_label = object_label or str(instance)[:200]

    if actor is None and request is not None:
        candidate = getattr(request, "user", None)
        if candidate is not None and candidate.is_authenticated:
            actor = candidate

    try:
        return AuditLog.objects.create(
            wedding=wedding,
            user=actor if getattr(actor, "pk", None) else None,
            actor_label=(getattr(actor, "email", "") or "sistema")[:160],
            action=action,
            model_name=model_name[:100],
            object_id=str(object_id)[:64],
            object_label=object_label[:200],
            old_data=sanitise(old_data),
            new_data=sanitise(new_data),
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception("Falha ao escrever registo de auditoria: %s", action)
        return None


def log_create(instance, actor=None, wedding=None, request=None) -> AuditLog | None:
    return log_action(
        action=AuditAction.CREATE,
        actor=actor,
        wedding=wedding or getattr(instance, "wedding", None),
        request=request,
        instance=instance,
        new_data=model_to_dict(instance),
    )


def log_update(instance, old_data: dict, actor=None, wedding=None, request=None) -> AuditLog | None:
    new_data = model_to_dict(instance)
    changed_old = {k: v for k, v in (old_data or {}).items() if new_data.get(k) != v}
    changed_new = {k: v for k, v in new_data.items() if (old_data or {}).get(k) != v}
    if not changed_new and not changed_old:
        return None
    return log_action(
        action=AuditAction.UPDATE,
        actor=actor,
        wedding=wedding or getattr(instance, "wedding", None),
        request=request,
        instance=instance,
        old_data=changed_old,
        new_data=changed_new,
    )


def log_delete(instance, actor=None, wedding=None, request=None) -> AuditLog | None:
    return log_action(
        action=AuditAction.DELETE,
        actor=actor,
        wedding=wedding or getattr(instance, "wedding", None),
        request=request,
        instance=instance,
        old_data=model_to_dict(instance),
    )
