from __future__ import annotations

from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("privacidade/", views.legal_page, {"page": "privacy"}, name="privacy"),
    path("termos/", views.legal_page, {"page": "terms"}, name="terms"),
    path("cookies/", views.legal_page, {"page": "cookies"}, name="cookies"),
    path("seguranca/", views.legal_page, {"page": "security"}, name="security"),
    path("contacto/", views.legal_page, {"page": "contact"}, name="contact"),
    path("estado/", views.health, name="health"),
]
