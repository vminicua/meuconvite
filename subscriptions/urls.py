from __future__ import annotations

from django.urls import path

from . import views

app_name = "subscriptions"

urlpatterns = [
    path("subscricao/", views.subscription_detail, name="detail"),
    path("subscricao/voucher/aplicar/", views.apply_voucher, name="apply_voucher"),
    path("subscricao/pacote/<slug:plan_code>/", views.upgrade, name="upgrade"),
    path("subscricao/pagamento/<str:reference>/", views.payment_detail, name="payment"),
    path("subscricao/pagamento/<str:reference>/sucesso/", views.payzeno_success, name="payzeno_success"),
    path("subscricao/pagamento/<str:reference>/cancelado/", views.payzeno_cancel, name="payzeno_cancel"),
    path("subscricao/pagamento/<str:reference>/verificar/", views.verify_payzeno, name="verify_payzeno"),
    path(
        "subscricao/pagamento/<str:reference>/cancelar/",
        views.cancel_payment,
        name="cancel_payment",
    ),
]
