"""
Área de administração da plataforma (equipa MeuConvite).

Páginas próprias, com layout de sidebar. O Django Admin continua
disponível para casos excepcionais, mas nenhuma tarefa do dia-a-dia
obriga a ir lá.

Todas as secções são servidas pela mesma casca (`shell.html`). Quando o
pedido vem do HTMX, só o conteúdo é devolvido — a troca de separador é
imediata e o URL é actualizado pelo `hx-push-url`.
"""

from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db import models
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from audit.models import AuditAction, AuditLog
from audit.services import log_action, log_update, model_to_dict
from events.models import EventCategory
from subscriptions import services as subscription_services
from subscriptions.models import Payment, PaymentProvider, PaymentStatus, Plan, Voucher
from subscriptions.payzeno import PayzenoError
from weddings.models import Wedding, WeddingStatus

from . import selectors
from .forms import (
    BlockEventForm,
    CategoryFieldForm,
    EventCategoryForm,
    PlanForm,
    PlatformConfigurationForm,
    VoucherForm,
)
from .models import PlatformConfiguration, configured_value


def _render(request: HttpRequest, section: str, template: str, context: dict) -> HttpResponse:
    """
    Devolve a secção dentro da casca, ou só a secção para o HTMX.

    É o que torna a navegação instantânea sem duplicar templates.
    """
    context = {**context, "section": section, "section_template": template}
    if request.headers.get("HX-Request") and not request.headers.get("HX-History-Restore-Request"):
        return render(request, template, context)
    return render(request, "platform_admin/shell.html", context)


# ---------------------------------------------------------------------
# Visão geral
# ---------------------------------------------------------------------


@staff_member_required
def dashboard(request: HttpRequest) -> HttpResponse:
    kpis = selectors.kpis()
    return _render(
        request,
        "dashboard",
        "platform_admin/sections/dashboard.html",
        {
            "kpis": kpis,
            "chart_events": json.dumps(selectors.events_per_month()),
            "chart_revenue": json.dumps(selectors.revenue_per_month()),
            "chart_categories": json.dumps(selectors.events_by_category()),
            "pending_payments": Payment.objects.filter(
                status__in=[
                    PaymentStatus.PENDING_GATEWAY,
                    PaymentStatus.AWAITING_PROOF,
                    PaymentStatus.UNDER_REVIEW,
                ]
            ).select_related("wedding", "plan")[:6],
            "recent_events": selectors.events_list()[:6],
            "recent_audit": AuditLog.objects.select_related("user").order_by("-created_at")[:10],
        },
    )


# ---------------------------------------------------------------------
# Eventos
# ---------------------------------------------------------------------


@staff_member_required
def events(request: HttpRequest) -> HttpResponse:
    search = request.GET.get("q", "").strip()
    status = request.GET.get("estado", "")
    category = request.GET.get("tipo", "")

    return _render(
        request,
        "events",
        "platform_admin/sections/events.html",
        {
            "events": selectors.events_list(search, status, category)[:500],
            "statuses": WeddingStatus.choices,
            "categories": EventCategory.objects.order_by("display_order", "name"),
            "search": search,
            "status": status,
            "category": category,
        },
    )


@staff_member_required
def event_detail(request: HttpRequest, wedding_id) -> HttpResponse:
    wedding = get_object_or_404(
        Wedding.objects.select_related("owner", "category"), pk=wedding_id
    )
    limits = subscription_services.limits(wedding)

    return _render(
        request,
        "events",
        "platform_admin/sections/event_detail.html",
        {
            "event": wedding,
            "limits": limits,
            "members": wedding.members.select_related("user").order_by("role"),
            "moments": wedding.events.order_by("date", "start_time"),
            "payments": wedding.payments.select_related("plan").order_by("-created_at"),
            "audit": AuditLog.objects.filter(wedding=wedding).order_by("-created_at")[:20],
            "block_form": BlockEventForm(),
        },
    )


@require_POST
@staff_member_required
def event_block(request: HttpRequest, wedding_id) -> HttpResponse:
    """
    Bloqueia ou desbloqueia um evento.

    Bloquear não apaga nada: o evento deixa de estar acessível ao cliente
    e as páginas públicas deixam de responder.
    """
    wedding = get_object_or_404(Wedding, pk=wedding_id)
    old_data = model_to_dict(wedding, fields=["status", "blocked_reason"])

    if wedding.status == WeddingStatus.BLOCKED:
        wedding.status = WeddingStatus.DRAFT
        wedding.blocked_reason = ""
        wedding.save(update_fields=["status", "blocked_reason", "updated_at"])
        messages.success(request, f"Evento «{wedding.display_names}» desbloqueado.")
    else:
        form = BlockEventForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Indique um motivo claro para bloquear o evento.")
            return redirect("platform:event_detail", wedding_id=wedding.pk)
        wedding.status = WeddingStatus.BLOCKED
        wedding.blocked_reason = form.cleaned_data["reason"]
        wedding.save(update_fields=["status", "blocked_reason", "updated_at"])
        messages.warning(request, f"Evento «{wedding.display_names}» bloqueado.")

    log_update(wedding, old_data=old_data, actor=request.user, wedding=wedding, request=request)
    return redirect("platform:event_detail", wedding_id=wedding.pk)


# ---------------------------------------------------------------------
# Utilizadores
# ---------------------------------------------------------------------


@staff_member_required
def users(request: HttpRequest) -> HttpResponse:
    search = request.GET.get("q", "").strip()
    role = request.GET.get("filtro", "")
    return _render(
        request,
        "users",
        "platform_admin/sections/users.html",
        {"users": selectors.users_list(search, role)[:500], "search": search, "role": role},
    )


@staff_member_required
def user_detail(request: HttpRequest, user_id) -> HttpResponse:
    from accounts.models import User

    person = get_object_or_404(User, pk=user_id)
    return _render(
        request,
        "users",
        "platform_admin/sections/user_detail.html",
        {
            "person": person,
            "owned": person.owned_weddings.select_related("category").order_by("-created_at"),
            "memberships": person.wedding_memberships.select_related("wedding").order_by("-created_at"),
            "audit": AuditLog.objects.filter(user=person).order_by("-created_at")[:20],
        },
    )


@require_POST
@staff_member_required
def user_toggle(request: HttpRequest, user_id) -> HttpResponse:
    """Activa/desactiva a conta ou o acesso de equipa."""
    from accounts.models import User

    person = get_object_or_404(User, pk=user_id)
    field = request.POST.get("campo")

    if person.pk == request.user.pk:
        messages.error(request, "Não pode alterar as suas próprias permissões aqui.")
        return redirect("platform:user_detail", user_id=person.pk)

    if field not in {"is_active", "is_staff"}:
        messages.error(request, "Alteração inválida.")
        return redirect("platform:user_detail", user_id=person.pk)

    old_data = model_to_dict(person, fields=[field])
    setattr(person, field, not getattr(person, field))
    person.save(update_fields=[field, "updated_at"])
    log_update(person, old_data=old_data, actor=request.user, request=request)

    label = "acesso de equipa" if field == "is_staff" else "conta"
    state = "activado" if getattr(person, field) else "desactivado"
    messages.success(request, f"{label.capitalize()} {state} para {person.email}.")
    return redirect("platform:user_detail", user_id=person.pk)


# ---------------------------------------------------------------------
# Pagamentos
# ---------------------------------------------------------------------


@staff_member_required
def payments(request: HttpRequest) -> HttpResponse:
    status = request.GET.get("estado", "abertos")
    queryset = Payment.objects.select_related("wedding", "plan", "requested_by", "reviewed_by")

    if status == "abertos":
        queryset = queryset.filter(
            status__in=[
                PaymentStatus.PENDING_GATEWAY,
                PaymentStatus.AWAITING_PROOF,
                PaymentStatus.UNDER_REVIEW,
            ]
        )
    elif status in dict(PaymentStatus.choices):
        queryset = queryset.filter(status=status)

    return _render(
        request,
        "payments",
        "platform_admin/sections/payments.html",
        {
            "payments": queryset.order_by("-created_at")[:200],
            "status": status,
            "statuses": PaymentStatus.choices,
            "instructions": subscription_services.payment_instructions(),
        },
    )


@require_POST
@staff_member_required
def payment_review(request: HttpRequest, reference: str) -> HttpResponse:
    payment = get_object_or_404(Payment, reference=reference)
    decision = request.POST.get("decisao")
    notes = (request.POST.get("notas") or "").strip()

    if decision == "confirmar":
        if payment.provider == PaymentProvider.PAYZENO:
            try:
                _payment, confirmed = subscription_services.verify_payzeno_payment(
                    payment=payment, request=request
                )
            except PayzenoError as exc:
                messages.error(request, str(exc))
                return redirect("platform:payments")
            if not confirmed:
                messages.warning(request, "A Payzeno ainda não confirma este pagamento.")
                return redirect("platform:payments")
        else:
            subscription_services.confirm_payment(
                payment=payment, actor=request.user, request=request, notes=notes
            )
        messages.success(
            request,
            f"Pagamento {payment.reference} confirmado — o pacote {payment.plan.name} "
            f"está activo em «{payment.wedding.display_names}».",
        )
    elif decision == "recusar":
        if not notes:
            messages.error(request, "Indique o motivo antes de recusar um pagamento.")
            return redirect("platform:payments")
        subscription_services.reject_payment(
            payment=payment, actor=request.user, request=request, notes=notes
        )
        messages.warning(request, f"Pagamento {payment.reference} recusado.")
    else:
        messages.error(request, "Decisão inválida.")

    return redirect("platform:payments")


# ---------------------------------------------------------------------
# Pacotes
# ---------------------------------------------------------------------


@staff_member_required
def plans(request: HttpRequest) -> HttpResponse:
    return _render(
        request,
        "plans",
        "platform_admin/sections/plans.html",
        {"plans": selectors.plans_list()},
    )


@staff_member_required
def settings_view(request: HttpRequest) -> HttpResponse:
    configuration = PlatformConfiguration.load()
    if request.method == "POST":
        form = PlatformConfigurationForm(request.POST, instance=configuration)
        if form.is_valid():
            form.save()
            messages.success(request, "Configurações da plataforma guardadas com segurança.")
            return redirect("platform:settings")
        messages.error(request, "Corrija os erros assinalados nas configurações.")
    else:
        form = PlatformConfigurationForm(instance=configuration)

    twilio_names = [name for name in PlatformConfigurationForm.SECRET_NAMES if name.startswith("twilio_")]
    twilio_status = {
        name: bool(configuration.get_secret(name) or configured_value(name))
        for name in twilio_names
    }
    twilio_status["twilio_sms_from"] = bool(configured_value("twilio_sms_from"))
    effective_payzeno = subscription_services.payzeno_configuration()
    payzeno_status = {
        "enabled": effective_payzeno["enabled"],
        "api_key": bool(effective_payzeno["api_key"]),
        "https": configuration.payzeno_base_url.startswith("https://"),
    }
    webhook_url = request.build_absolute_uri(reverse("payzeno_webhook"))
    return _render(
        request,
        "settings",
        "platform_admin/sections/settings.html",
        {
            "form": form,
            "configuration": configuration,
            "twilio_status": twilio_status,
            "payzeno_status": payzeno_status,
            "payzeno_webhook_url": webhook_url,
        },
    )


@staff_member_required
def plan_form(request: HttpRequest, plan_id=None) -> HttpResponse:
    plan = get_object_or_404(Plan, pk=plan_id) if plan_id else None

    if request.method == "POST":
        form = PlanForm(request.POST, instance=plan)
        if form.is_valid():
            old_data = model_to_dict(plan) if plan else {}
            saved = form.save()
            if plan:
                log_update(saved, old_data=old_data, actor=request.user, request=request)
            else:
                log_action(
                    action=AuditAction.CREATE, actor=request.user, request=request, instance=saved
                )
            messages.success(request, f"Pacote «{saved.name}» guardado.")
            return redirect("platform:plans")
        messages.error(request, "Corrija os erros assinalados.")
    else:
        form = PlanForm(instance=plan)

    return _render(
        request,
        "plans",
        "platform_admin/sections/plan_form.html",
        {"form": form, "plan": plan},
    )


# ---------------------------------------------------------------------
# Vouchers
# ---------------------------------------------------------------------


@staff_member_required
def vouchers(request: HttpRequest) -> HttpResponse:
    queryset = Voucher.objects.annotate(redemption_total=models.Count("redemptions"))
    return _render(
        request, "vouchers", "platform_admin/sections/vouchers.html",
        {"vouchers": queryset.order_by("-created_at")},
    )


@staff_member_required
def voucher_form(request: HttpRequest, voucher_id=None) -> HttpResponse:
    voucher = get_object_or_404(Voucher, pk=voucher_id) if voucher_id else None
    if request.method == "POST":
        form = VoucherForm(request.POST, instance=voucher)
        if form.is_valid():
            old_data = model_to_dict(voucher) if voucher else {}
            saved = form.save()
            if voucher:
                log_update(saved, old_data=old_data, actor=request.user, request=request)
            else:
                log_action(action=AuditAction.CREATE, actor=request.user, request=request, instance=saved)
            messages.success(request, f"Voucher «{saved.code}» guardado.")
            return redirect("platform:vouchers")
        messages.error(request, "Corrija os erros assinalados.")
    else:
        form = VoucherForm(instance=voucher)
    return _render(
        request, "vouchers", "platform_admin/sections/voucher_form.html",
        {"form": form, "voucher": voucher},
    )


# ---------------------------------------------------------------------
# Tipos de evento
# ---------------------------------------------------------------------


@staff_member_required
def categories(request: HttpRequest) -> HttpResponse:
    return _render(
        request,
        "categories",
        "platform_admin/sections/categories.html",
        {"categories": selectors.categories_list()},
    )


@staff_member_required
def category_form(request: HttpRequest, category_id=None) -> HttpResponse:
    category = get_object_or_404(EventCategory, pk=category_id) if category_id else None

    if request.method == "POST":
        form = EventCategoryForm(request.POST, instance=category)
        if form.is_valid():
            old_data = model_to_dict(category) if category else {}
            saved = form.save()
            if category:
                log_update(saved, old_data=old_data, actor=request.user, request=request)
            else:
                log_action(
                    action=AuditAction.CREATE, actor=request.user, request=request, instance=saved
                )
            messages.success(request, f"Tipo de evento «{saved.name}» guardado.")
            return redirect("platform:category_edit", category_id=saved.pk)
        messages.error(request, "Corrija os erros assinalados.")
    else:
        form = EventCategoryForm(instance=category)

    return _render(
        request,
        "categories",
        "platform_admin/sections/category_form.html",
        {
            "form": form,
            "category": category,
            "field_form": CategoryFieldForm(category=category),
            "fields": category.extra_fields if category else [],
        },
    )


@require_POST
@staff_member_required
def category_field_add(request: HttpRequest, category_id) -> HttpResponse:
    category = get_object_or_404(EventCategory, pk=category_id)
    form = CategoryFieldForm(request.POST, category=category)

    if form.is_valid():
        try:
            schema = list(category.field_schema or []) + [form.definition()]
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            old_data = {"field_schema": len(category.field_schema or [])}
            category.field_schema = schema
            category.save(update_fields=["field_schema", "updated_at"])
            log_update(category, old_data=old_data, actor=request.user, request=request)
            messages.success(request, f"Campo «{form.cleaned_data['label']}» acrescentado.")
    else:
        messages.error(request, "Não foi possível acrescentar o campo.")

    return redirect("platform:category_edit", category_id=category.pk)


@require_POST
@staff_member_required
def category_field_remove(request: HttpRequest, category_id, key: str) -> HttpResponse:
    category = get_object_or_404(EventCategory, pk=category_id)
    old_data = {"field_schema": len(category.field_schema or [])}
    category.field_schema = [
        definition
        for definition in (category.field_schema or [])
        if isinstance(definition, dict) and definition.get("key") != key
    ]
    category.save(update_fields=["field_schema", "updated_at"])
    log_update(category, old_data=old_data, actor=request.user, request=request)
    messages.info(request, "Campo removido.")
    return redirect("platform:category_edit", category_id=category.pk)


# ---------------------------------------------------------------------
# Templates de convite
# ---------------------------------------------------------------------


@staff_member_required
def templates(request: HttpRequest) -> HttpResponse:
    from templates_manager.models import InvitationTemplate

    return _render(
        request,
        "templates",
        "platform_admin/sections/templates.html",
        {
            "templates": InvitationTemplate.objects.prefetch_related("categories").order_by(
                "-is_featured", "display_order", "name"
            )
        },
    )


@staff_member_required
def template_form(request: HttpRequest, template_id=None) -> HttpResponse:
    from templates_manager.models import InvitationTemplate

    from .forms import InvitationTemplateForm

    template = get_object_or_404(InvitationTemplate, pk=template_id) if template_id else None

    if request.method == "POST":
        form = InvitationTemplateForm(request.POST, request.FILES, instance=template)
        if form.is_valid():
            old_data = model_to_dict(template) if template else {}
            saved = form.save()
            if template:
                log_update(saved, old_data=old_data, actor=request.user, request=request)
            else:
                log_action(
                    action=AuditAction.CREATE, actor=request.user, request=request, instance=saved
                )
            messages.success(request, f"Template «{saved.name}» guardado.")
            return redirect("platform:templates")
        messages.error(request, "Corrija os erros assinalados.")
    else:
        form = InvitationTemplateForm(instance=template)

    return _render(
        request,
        "templates",
        "platform_admin/sections/template_form.html",
        {"form": form, "template": template},
    )


@staff_member_required
@xframe_options_sameorigin
def template_preview(request: HttpRequest, template_id) -> HttpResponse:
    """Preview móvel completo de um template dentro da administração."""
    from templates_manager.models import InvitationTemplate
    from templates_manager.services import DEMO_GUEST_NAME, invitation_context

    template = get_object_or_404(InvitationTemplate, pk=template_id)
    wedding = Wedding.objects.select_related("category", "owner").order_by("-created_at").first()
    if wedding is None:
        return HttpResponse(
            '<div style="font-family:system-ui;padding:2rem;text-align:center">Crie um evento para visualizar este template.</div>'
        )
    context = invitation_context(
        wedding,
        template,
        guest_name=DEMO_GUEST_NAME,
        seats=2,
        is_preview=True,
        use_event_colours=False,
    )
    context["embedded"] = True
    return render(request, "invitations/preview.html", context)


# ---------------------------------------------------------------------
# Auditoria
# ---------------------------------------------------------------------


@staff_member_required
def audit(request: HttpRequest) -> HttpResponse:
    action = request.GET.get("accao", "")
    search = request.GET.get("q", "").strip()
    return _render(
        request,
        "audit",
        "platform_admin/sections/audit.html",
        {
            "entries": selectors.audit_list(action, search)[:500],
            "actions": AuditAction.choices,
            "action": action,
            "search": search,
        },
    )
