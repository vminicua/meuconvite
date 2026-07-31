from __future__ import annotations

from django.urls import path

from . import views

app_name = "platform"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    # Eventos
    path("eventos/", views.events, name="events"),
    path("eventos/<uuid:wedding_id>/", views.event_detail, name="event_detail"),
    path("eventos/<uuid:wedding_id>/bloquear/", views.event_block, name="event_block"),
    # Utilizadores
    path("utilizadores/", views.users, name="users"),
    path("utilizadores/<uuid:user_id>/", views.user_detail, name="user_detail"),
    path("utilizadores/<uuid:user_id>/alterar/", views.user_toggle, name="user_toggle"),
    # Pagamentos
    path("pagamentos/", views.payments, name="payments"),
    path("pagamentos/<str:reference>/", views.payment_review, name="payment_review"),
    # Pacotes
    path("pacotes/", views.plans, name="plans"),
    path("pacotes/novo/", views.plan_form, name="plan_create"),
    path("pacotes/<uuid:plan_id>/", views.plan_form, name="plan_edit"),
    # Tipos de evento
    path("tipos/", views.categories, name="categories"),
    path("tipos/novo/", views.category_form, name="category_create"),
    path("tipos/<uuid:category_id>/", views.category_form, name="category_edit"),
    path("tipos/<uuid:category_id>/campos/", views.category_field_add, name="category_field_add"),
    path(
        "tipos/<uuid:category_id>/campos/<slug:key>/remover/",
        views.category_field_remove,
        name="category_field_remove",
    ),
    # Templates de convite
    path("templates/", views.templates, name="templates"),
    path("templates/novo/", views.template_form, name="template_create"),
    path("templates/<uuid:template_id>/", views.template_form, name="template_edit"),
    # Auditoria
    path("auditoria/", views.audit, name="audit"),
]
