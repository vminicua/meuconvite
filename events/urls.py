from __future__ import annotations

from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("organizacao/", views.organisation, name="organisation"),
    # Events
    path("eventos/", views.event_list, name="list"),
    path("eventos/novo/", views.event_create, name="create"),
    path("eventos/ordenar/", views.event_reorder, name="reorder"),
    path("eventos/<uuid:event_id>/", views.event_edit, name="edit"),
    path("eventos/<uuid:event_id>/eliminar/", views.event_delete, name="delete"),
    # Locations
    path("locais/", views.location_list, name="location_list"),
    path("locais/novo/", views.location_create, name="location_create"),
    path("locais/<uuid:location_id>/", views.location_edit, name="location_edit"),
    path("locais/<uuid:location_id>/eliminar/", views.location_delete, name="location_delete"),
    # Programme
    path("programa/", views.schedule, name="schedule"),
    path(
        "programa/campos/<slug:key>/remover/",
        views.schedule_field_delete,
        name="schedule_field_delete",
    ),
    path("programa/novo/", views.schedule_create, name="schedule_create"),
    path("programa/ordenar/", views.schedule_reorder, name="schedule_reorder"),
    path("programa/<uuid:item_id>/", views.schedule_edit, name="schedule_edit"),
    path("programa/<uuid:item_id>/eliminar/", views.schedule_delete, name="schedule_delete"),
]
