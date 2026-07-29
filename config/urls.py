"""Root URL configuration for MeuConvite."""

from __future__ import annotations

import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

# The Django admin path can be moved via the environment to reduce noise
# from automated scanners in production.
ADMIN_URL = os.environ.get("DJANGO_ADMIN_URL", "django-admin/").strip("/") + "/"

admin.site.site_header = "MeuConvite — Administração"
admin.site.site_title = "MeuConvite"
admin.site.index_title = "Gestão da plataforma"

urlpatterns = [
    path(ADMIN_URL, admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("perfil/", include("accounts.urls", namespace="accounts")),
    path("casamentos/", include("weddings.urls", namespace="weddings")),
    path("casamentos/<uuid:wedding_id>/", include("events.urls", namespace="events")),
    path("", include("core.urls", namespace="core")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
