"""Reusable backend validators (never rely on frontend validation alone)."""

from __future__ import annotations

import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as _

HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
PHONE_RE = re.compile(r"^\+?\d{7,15}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Slugs reserved by the platform: they must never be taken by a wedding.
RESERVED_SLUGS = {
    "admin",
    "accounts",
    "account",
    "api",
    "checkin",
    "check-in",
    "casamentos",
    "eventos",
    "convite",
    "invite",
    "perfil",
    "static",
    "media",
    "painel",
    "administracao",
    "dashboard",
    "planos",
    "precos",
    "suporte",
    "sobre",
    "contacto",
    "privacidade",
    "termos",
    "django-admin",
    "meuconvite",
    "www",
}


def validate_hex_color(value: str) -> None:
    if value and not HEX_COLOR_RE.match(value):
        raise ValidationError(
            _("Introduza uma cor válida no formato hexadecimal, por exemplo #C8A96A.")
        )


def validate_phone(value: str) -> None:
    if value and not PHONE_RE.match(value.replace(" ", "")):
        raise ValidationError(
            _("Introduza um número de telefone válido, por exemplo +258 84 123 4567.")
        )


def validate_wedding_slug(value: str) -> None:
    if not SLUG_RE.match(value or ""):
        raise ValidationError(
            _("O endereço só pode conter letras minúsculas, números e hífenes.")
        )
    if value in RESERVED_SLUGS:
        raise ValidationError(_("Este endereço está reservado. Escolha outro."))


@deconstructible
class FileValidator:
    """
    Validates uploaded files by size, extension and content type.

    Content type is checked against the browser-provided value *and* the
    real file signature when Pillow can open it, so a renamed `.exe`
    cannot pass as an image.
    """

    def __init__(
        self,
        max_size: int,
        allowed_extensions: list[str],
        allowed_content_types: list[str] | None = None,
        verify_image: bool = False,
    ) -> None:
        self.max_size = max_size
        self.allowed_extensions = [ext.lower() for ext in allowed_extensions]
        self.allowed_content_types = allowed_content_types or []
        self.verify_image = verify_image

    def __call__(self, file_obj) -> None:
        if not file_obj:
            return

        size = getattr(file_obj, "size", 0)
        if size and size > self.max_size:
            raise ValidationError(
                _("O ficheiro é demasiado grande. Tamanho máximo: %(max)s MB.")
                % {"max": round(self.max_size / (1024 * 1024), 1)}
            )

        name = (getattr(file_obj, "name", "") or "").lower()
        extension = name.rsplit(".", 1)[-1] if "." in name else ""
        if extension not in self.allowed_extensions:
            raise ValidationError(
                _("Formato não permitido. Formatos aceites: %(formats)s.")
                % {"formats": ", ".join(self.allowed_extensions)}
            )

        content_type = getattr(file_obj, "content_type", None)
        if content_type and self.allowed_content_types:
            if content_type.lower() not in self.allowed_content_types:
                raise ValidationError(
                    _("O tipo de ficheiro (%(type)s) não é permitido.")
                    % {"type": content_type}
                )

        if self.verify_image:
            self._verify_image(file_obj)

    @staticmethod
    def _verify_image(file_obj) -> None:
        from PIL import Image, UnidentifiedImageError

        try:
            position = file_obj.tell()
        except (AttributeError, OSError):
            position = 0
        try:
            file_obj.seek(0)
            with Image.open(file_obj) as image:
                image.verify()
        except (UnidentifiedImageError, OSError, ValueError):
            raise ValidationError(
                _("O ficheiro não é uma imagem válida.")
            ) from None
        finally:
            try:
                file_obj.seek(position)
            except (AttributeError, OSError):
                pass

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, FileValidator)
            and self.max_size == other.max_size
            and self.allowed_extensions == other.allowed_extensions
            and self.allowed_content_types == other.allowed_content_types
            and self.verify_image == other.verify_image
        )


def _build_image_validator() -> FileValidator:
    return FileValidator(
        max_size=getattr(settings, "MAX_IMAGE_UPLOAD_SIZE", 5 * 1024 * 1024),
        allowed_extensions=getattr(
            settings, "ALLOWED_IMAGE_EXTENSIONS", ["jpg", "jpeg", "png", "webp"]
        ),
        allowed_content_types=getattr(
            settings,
            "ALLOWED_IMAGE_CONTENT_TYPES",
            ["image/jpeg", "image/png", "image/webp"],
        ),
        verify_image=True,
    )


def validate_image_upload(file_obj) -> None:
    """Module level callable so migrations stay stable."""
    _build_image_validator()(file_obj)


def validate_audio_upload(file_obj) -> None:
    FileValidator(
        max_size=getattr(settings, "MAX_AUDIO_UPLOAD_SIZE", 8 * 1024 * 1024),
        allowed_extensions=getattr(settings, "ALLOWED_AUDIO_EXTENSIONS", ["mp3", "m4a", "ogg"]),
    )(file_obj)


def validate_spreadsheet_upload(file_obj) -> None:
    FileValidator(
        max_size=getattr(settings, "MAX_SPREADSHEET_UPLOAD_SIZE", 5 * 1024 * 1024),
        allowed_extensions=getattr(settings, "ALLOWED_SPREADSHEET_EXTENSIONS", ["xlsx"]),
    )(file_obj)
