from __future__ import annotations

from django.urls import path

from . import views

app_name = "subscriptions"

urlpatterns = [
    path("subscricao/", views.subscription_detail, name="detail"),
    path("subscricao/pacote/<slug:plan_code>/", views.upgrade, name="upgrade"),
    path("subscricao/pagamento/<str:reference>/", views.payment_detail, name="payment"),
    path(
        "subscricao/pagamento/<str:reference>/cancelar/",
        views.cancel_payment,
        name="cancel_payment",
    ),
]
