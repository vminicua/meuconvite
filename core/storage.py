"""
Upload path helpers.

All media paths are derived from UUIDs, never from user supplied file
names, which avoids path traversal and keeps filenames predictable.
Switching to S3/Azure later only requires changing `STORAGES["default"]`
in the settings — these helpers stay unchanged.
"""

from __future__ import annotations

import uuid
from pathlib import Path


def _safe_extension(filename: str, fallback: str = "bin") -> str:
    suffix = Path(filename or "").suffix.lower().lstrip(".")
    if not suffix or not suffix.isalnum() or len(suffix) > 5:
        return fallback
    return suffix


def _build_path(prefix: str, wedding_id, filename: str, fallback_ext: str = "jpg") -> str:
    extension = _safe_extension(filename, fallback_ext)
    return f"{prefix}/{wedding_id}/{uuid.uuid4().hex}.{extension}"


def wedding_cover_upload_to(instance, filename: str) -> str:
    return _build_path("weddings/covers", instance.pk or uuid.uuid4(), filename)


def wedding_gallery_upload_to(instance, filename: str) -> str:
    wedding_id = getattr(instance, "wedding_id", None) or uuid.uuid4()
    return _build_path("weddings/gallery", wedding_id, filename)


def wedding_music_upload_to(instance, filename: str) -> str:
    return _build_path("weddings/music", instance.pk or uuid.uuid4(), filename, "mp3")


def music_track_upload_to(instance, filename: str) -> str:
    return _build_path("music/library", instance.pk or uuid.uuid4(), filename, "mp3")


def user_avatar_upload_to(instance, filename: str) -> str:
    return _build_path("users/avatars", instance.pk or uuid.uuid4(), filename)


def template_cover_upload_to(instance, filename: str) -> str:
    return _build_path("templates/covers", instance.pk or uuid.uuid4(), filename)


def template_music_upload_to(instance, filename: str) -> str:
    return _build_path("templates/music", instance.pk or uuid.uuid4(), filename, "mp3")
