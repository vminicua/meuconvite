from django.urls import path

from . import views

app_name = "guests"

urlpatterns = [
    path("convidados/", views.guest_list, name="list"),
    path("convidados/exportar-excel/", views.guest_export_excel, name="export_excel"),
    path("convidados/modelo-importacao/", views.guest_import_template, name="import_template"),
    path("convidados/importar-excel/", views.guest_import_excel, name="import_excel"),
    path("convidados/enviar-em-lote/", views.guest_bulk_send, name="bulk_send"),
    path("convidados/<uuid:guest_id>/", views.guest_edit, name="edit"),
    path("convidados/<uuid:guest_id>/enviar/", views.guest_send_invitation, name="send_invitation"),
    path("convidados/<uuid:guest_id>/remover/", views.guest_remove, name="remove"),
    path(
        "convidados/<uuid:guest_id>/acesso-plano/",
        views.guest_plan_access,
        name="plan_access",
    ),
    path("presentes/", views.gift_list, name="gifts"),
    path("presentes/<uuid:gift_id>/editar/", views.gift_edit, name="gift_edit"),
    path("presentes/<uuid:gift_id>/remover/", views.gift_remove, name="gift_remove"),
]
