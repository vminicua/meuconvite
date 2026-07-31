from django.urls import path

from . import views

app_name = "guests"

urlpatterns = [
    path("convidados/", views.guest_list, name="list"),
    path("convidados/<uuid:guest_id>/", views.guest_edit, name="edit"),
    path("convidados/<uuid:guest_id>/remover/", views.guest_remove, name="remove"),
]
