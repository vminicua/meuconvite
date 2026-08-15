from __future__ import annotations

from django.urls import path

from . import views

app_name = "weddings"

urlpatterns = [
    path("", views.wedding_list, name="list"),
    path("novo/", views.wedding_create, name="create"),
    path("<uuid:wedding_id>/", views.wedding_detail, name="detail"),
    path("<uuid:wedding_id>/convite/", views.wedding_preview, name="preview"),
    path("<uuid:wedding_id>/assistente/", views.wedding_setup, name="setup"),
    path("<uuid:wedding_id>/definicoes/", views.wedding_settings, name="settings"),
    path("<uuid:wedding_id>/aspecto/", views.wedding_design, name="design"),
    path("<uuid:wedding_id>/galeria/", views.wedding_gallery, name="gallery"),
    path(
        "<uuid:wedding_id>/galeria/<uuid:photo_id>/actualizar/",
        views.gallery_photo_update,
        name="gallery_photo_update",
    ),
    path(
        "<uuid:wedding_id>/galeria/<uuid:photo_id>/mover/",
        views.gallery_photo_move,
        name="gallery_photo_move",
    ),
    path(
        "<uuid:wedding_id>/galeria/<uuid:photo_id>/remover/",
        views.gallery_photo_delete,
        name="gallery_photo_delete",
    ),
    path(
        "<uuid:wedding_id>/convite/pre-visualizar/",
        views.invitation_preview,
        name="invitation_preview",
    ),
    path(
        "<uuid:wedding_id>/convite/pre-visualizar/<slug:template_code>/",
        views.invitation_preview,
        name="invitation_preview_template",
    ),
    path("<uuid:wedding_id>/publicar/", views.wedding_publish, name="publish"),
    path("<uuid:wedding_id>/arquivar/", views.wedding_archive, name="archive"),
    path("<uuid:wedding_id>/equipa/", views.team_list, name="team"),
    path("<uuid:wedding_id>/equipa/<uuid:member_id>/", views.team_edit, name="team_edit"),
    path(
        "<uuid:wedding_id>/equipa/<uuid:member_id>/remover/",
        views.team_remove,
        name="team_remove",
    ),
]
