"""Root URL configuration for MeuConvite."""

from __future__ import annotations

import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from subscriptions import views as subscription_views
from guests import views as guest_views

# The Django admin path can be moved via the environment to reduce noise
# from automated scanners in production.
ADMIN_URL = os.environ.get("DJANGO_ADMIN_URL", "django-admin/").strip("/") + "/"

admin.site.site_header = "MeuConvite — Administração"
admin.site.site_title = "MeuConvite"
admin.site.index_title = "Gestão da plataforma"

urlpatterns = [
    path(ADMIN_URL, admin.site.urls),
    # A plataforma deixou de ser só para casamentos: o endereço passou a ser
    # /eventos/. Este redireccionamento evita que ligações já abertas ou
    # guardadas nos favoritos deixem de funcionar.
    path(
        "casamentos/<path:resto>",
        RedirectView.as_view(url="/eventos/%(resto)s", permanent=False),
    ),
    path("casamentos/", RedirectView.as_view(pattern_name="weddings:list", permanent=False)),
    path("accounts/", include("allauth.urls")),
    path("perfil/", include("accounts.urls", namespace="accounts")),
    path("subscricao/", subscription_views.account_subscription, name="account_subscription"),
    path("convite/<str:token>/", guest_views.guest_invitation, name="guest_invitation"),
    # Área da equipa MeuConvite (exige is_staff).
    path("administracao/", include("platform_admin.urls", namespace="platform")),
    path("eventos/", include("weddings.urls", namespace="weddings")),
    path("eventos/<uuid:wedding_id>/", include("guests.urls", namespace="guests")),
    path("eventos/<uuid:wedding_id>/", include("events.urls", namespace="events")),
    path(
        "eventos/<uuid:wedding_id>/",
        include("subscriptions.urls", namespace="subscriptions"),
    ),
    path("", include("core.urls", namespace="core")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
