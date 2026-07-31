from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.decorators.clickjacking import xframe_options_sameorigin

from audit.services import model_to_dict

from . import services
from .forms import (
    MemberInviteForm,
    MemberPermissionsForm,
    WeddingCreateForm,
    WeddingDesignForm,
    WeddingSettingsForm,
)
from .models import WeddingMember
from .permissions import capability_flags, require_wedding, user_can
from .selectors import (
    archived_weddings_for_user,
    categories_with_templates,
    dashboard_summary,
    team_members,
    upcoming_events,
    weddings_for_user,
)

# ---------------------------------------------------------------------
# Wedding list & creation
# ---------------------------------------------------------------------


@login_required
def wedding_list(request: HttpRequest) -> HttpResponse:
    """
    Eventos do utilizador.

    Os tipos de evento aparecem logo no topo: criar um evento novo passa a
    ser um clique, sem passar por um ecrã intermédio.
    """
    categories = categories_with_templates()

    return render(
        request,
        "weddings/wedding_list.html",
        {
            "weddings": weddings_for_user(request.user),
            "archived": archived_weddings_for_user(request.user),
            "categories": categories,
        },
    )


@login_required
def wedding_create(request: HttpRequest) -> HttpResponse:
    """
    Criação de um evento, em dois ecrãs simples.

    Sem `?tipo=`, mostra os tipos de evento disponíveis. Com o tipo
    escolhido, mostra um formulário curto, com as etiquetas e os campos
    próprios desse tipo.
    """
    from events.models import EventCategory
    from templates_manager import registry

    categories = list(EventCategory.objects.active().order_by("display_order", "name"))
    code = request.GET.get("tipo") or request.POST.get("category")
    category = next((item for item in categories if item.code == code), None)

    if category is None:
        return render(
            request,
            "weddings/event_type_choice.html",
            {"categories": categories},
        )

    # Passo 2: escolher o template do convite antes de preencher os dados.
    template_code = request.GET.get("template") or request.POST.get("template")
    template = registry.get_template(template_code) if template_code else None
    if template is None or template.code != template_code:
        return render(
            request,
            "weddings/template_choice.html",
            {
                "category": category,
                "templates": registry.all_templates(category),
            },
        )

    if request.method == "POST":
        form = WeddingCreateForm(request.POST, category=category)
        if form.is_valid():
            data = form.wedding_data()
            data["selected_template"] = template.code
            data["primary_color"] = template.primary
            data["secondary_color"] = template.secondary
            wedding = services.create_wedding(
                owner=request.user,
                data=data,
                category=category,
                extra_data={},
                request=request,
            )
            messages.success(
                request,
                f"{category.name} criado. Já criámos os momentos e o programa habituais — "
                "reveja e ajuste ao seu gosto.",
            )
            return redirect("weddings:preview", wedding_id=wedding.pk)
        messages.error(request, "Corrija os erros assinalados no formulário.")
    else:
        form = WeddingCreateForm(category=category)

    return render(
        request,
        "weddings/wedding_form.html",
        {
            "form": form,
            "category": category,
            "categories": categories,
            "template": template,
        },
    )


# ---------------------------------------------------------------------
# Dashboard & settings
# ---------------------------------------------------------------------


@require_wedding()
def wedding_preview(request: HttpRequest, wedding) -> HttpResponse:
    """Workspace preview: the first tab shows the invitation with current event data."""
    return render(
        request,
        "weddings/wedding_preview.html",
        {"wedding": wedding, "capabilities": capability_flags(wedding, request.user)},
    )


@require_wedding()
def wedding_detail(request: HttpRequest, wedding) -> HttpResponse:
    """Painel do evento."""
    from subscriptions import services as subscription_services

    limits = subscription_services.limits(wedding)
    guests_used = subscription_services.guest_count(wedding)

    return render(
        request,
        "weddings/wedding_detail.html",
        {
            "wedding": wedding,
            "summary": dashboard_summary(wedding),
            "checklist": services.build_checklist(wedding),
            "events": upcoming_events(wedding),
            "limits": limits,
            "guests_used": guests_used,
            "guests_remaining": limits.guests_remaining(guests_used),
            "usage_percent": limits.usage_percent(guests_used),
            "capabilities": capability_flags(wedding, request.user),
        },
    )


@require_wedding()
def wedding_setup(request: HttpRequest, wedding) -> HttpResponse:
    """Wizard overview: what is done and what is still missing."""
    checklist = services.build_checklist(wedding)
    done = sum(1 for item in checklist if item.done)
    return render(
        request,
        "weddings/wedding_setup.html",
        {
            "wedding": wedding,
            "checklist": checklist,
            "progress": int(done / len(checklist) * 100) if checklist else 0,
            "can_publish": not services.missing_requirements(wedding),
            "capabilities": capability_flags(wedding, request.user),
        },
    )


@require_wedding()
def wedding_settings(request: HttpRequest, wedding) -> HttpResponse:
    if not user_can(wedding, request.user, "can_manage_events"):
        raise Http404

    if request.method == "POST":
        form = WeddingSettingsForm(request.POST, instance=wedding)
        if form.is_valid():
            # Os campos `extra__*` do esquema do tipo de evento não são
            # colunas: vão todos para `extra_data`.
            data = {
                key: value
                for key, value in form.cleaned_data.items()
                if not key.startswith("extra__")
            }
            data["extra_data"] = form.extra_data()
            services.update_wedding(
                wedding=wedding,
                data=data,
                actor=request.user,
                request=request,
            )
            messages.success(request, "Definições actualizadas.")
            return redirect("weddings:settings", wedding_id=wedding.pk)
        messages.error(request, "Corrija os erros assinalados no formulário.")
    else:
        form = WeddingSettingsForm(instance=wedding)

    return render(
        request,
        "weddings/wedding_settings.html",
        {"wedding": wedding, "form": form, "capabilities": capability_flags(wedding, request.user)},
    )


@require_wedding("can_manage_design")
def wedding_design(request: HttpRequest, wedding) -> HttpResponse:
    """Template, colours, cover photo and music."""
    if request.method == "POST":
        form = WeddingDesignForm(request.POST, request.FILES, instance=wedding)
        if form.is_valid():
            old_data = model_to_dict(wedding)
            form.save()
            from audit.services import log_update

            log_update(
                wedding, old_data=old_data, actor=request.user, wedding=wedding, request=request
            )
            messages.success(request, "Aspecto do convite actualizado.")
            return redirect("weddings:design", wedding_id=wedding.pk)
        messages.error(request, "Corrija os erros assinalados no formulário.")
    else:
        form = WeddingDesignForm(instance=wedding)

    from templates_manager import registry

    return render(
        request,
        "weddings/wedding_design.html",
        {
            "wedding": wedding,
            "form": form,
            "templates": registry.all_templates(wedding.category),
            "selected_template": registry.get_template(wedding.selected_template),
            "capabilities": capability_flags(wedding, request.user),
        },
    )


@xframe_options_sameorigin
@require_wedding()
def invitation_preview(request: HttpRequest, wedding, template_code: str = "") -> HttpResponse:
    """
    Mostra o convite como o convidado o verá.

    Serve para experimentar templates antes de decidir: se o código vier
    no URL, é esse que é desenhado; caso contrário usa-se o do evento.
    """
    from templates_manager import registry, services as template_services

    template = registry.get_template(template_code or wedding.selected_template)
    if template is None:
        raise Http404

    context = template_services.invitation_context(
        wedding,
        template,
        guest_name=template_services.DEMO_GUEST_NAME,
        seats=2,
        is_preview=True,
        use_event_colours=template.code == wedding.selected_template,
    )
    context["embedded"] = request.GET.get("embedded") == "1"
    return render(request, "invitations/preview.html", context)


# ---------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------


@require_POST
@require_wedding()
def wedding_publish(request: HttpRequest, wedding) -> HttpResponse:
    if not user_can(wedding, request.user, "can_manage_events"):
        raise Http404
    try:
        services.publish_wedding(wedding=wedding, actor=request.user, request=request)
    except ValidationError as exc:
        for message in exc.messages:
            messages.error(request, message)
        return redirect("weddings:setup", wedding_id=wedding.pk)
    except PermissionDenied as exc:
        messages.error(request, str(exc))
        return redirect("weddings:detail", wedding_id=wedding.pk)

    messages.success(request, "Evento publicado. A página pública já está disponível.")
    return redirect("weddings:detail", wedding_id=wedding.pk)


@require_POST
@require_wedding()
def wedding_unpublish(request: HttpRequest, wedding) -> HttpResponse:
    if not user_can(wedding, request.user, "can_manage_events"):
        raise Http404
    services.unpublish_wedding(wedding=wedding, actor=request.user, request=request)
    messages.info(request, "Evento despublicado. As páginas públicas deixaram de responder.")
    return redirect("weddings:detail", wedding_id=wedding.pk)


@require_POST
@require_wedding()
def wedding_archive(request: HttpRequest, wedding) -> HttpResponse:
    """
    Archiving hides the wedding without deleting anything.

    There is no destructive delete in the interface on purpose: guest and
    check-in history must remain available to the couple.
    """
    if wedding.owner_id != request.user.pk:
        raise Http404
    services.archive_wedding(wedding=wedding, actor=request.user, request=request)
    messages.info(request, "Evento arquivado. Nenhum dado foi eliminado.")
    return redirect("weddings:list")


# ---------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------


@require_wedding()
def team_list(request: HttpRequest, wedding) -> HttpResponse:
    capabilities = capability_flags(wedding, request.user)
    if not capabilities["manage_members"] and not capabilities["is_owner"]:
        raise Http404

    form = MemberInviteForm(wedding=wedding)
    if request.method == "POST":
        form = MemberInviteForm(request.POST, wedding=wedding)
        if form.is_valid():
            services.add_member(
                wedding=wedding,
                user=form.user,
                role=form.cleaned_data["role"],
                actor=request.user,
                request=request,
                notes=form.cleaned_data.get("notes", ""),
            )
            messages.success(request, "Membro adicionado à equipa.")
            return redirect("weddings:team", wedding_id=wedding.pk)
        messages.error(request, "Não foi possível adicionar o membro.")

    return render(
        request,
        "weddings/team_list.html",
        {
            "wedding": wedding,
            "members": team_members(wedding),
            "form": form,
            "capabilities": capabilities,
        },
    )


@require_wedding()
def team_edit(request: HttpRequest, wedding, member_id) -> HttpResponse:
    capabilities = capability_flags(wedding, request.user)
    if not capabilities["manage_members"] and not capabilities["is_owner"]:
        raise Http404

    membership = get_object_or_404(WeddingMember, pk=member_id, wedding=wedding)
    if membership.user_id == wedding.owner_id:
        messages.error(request, "As permissões do proprietário não podem ser alteradas.")
        return redirect("weddings:team", wedding_id=wedding.pk)

    if request.method == "POST":
        form = MemberPermissionsForm(request.POST, instance=membership)
        if form.is_valid():
            services.update_member(
                membership=membership,
                role=form.cleaned_data["role"],
                permissions={
                    key: value
                    for key, value in form.cleaned_data.items()
                    if key.startswith("can_")
                },
                actor=request.user,
                request=request,
            )
            messages.success(request, "Permissões actualizadas.")
            return redirect("weddings:team", wedding_id=wedding.pk)
        messages.error(request, "Corrija os erros assinalados no formulário.")
    else:
        form = MemberPermissionsForm(instance=membership)

    return render(
        request,
        "weddings/team_form.html",
        {
            "wedding": wedding,
            "membership": membership,
            "form": form,
            "capabilities": capabilities,
        },
    )


@require_POST
@require_wedding()
def team_remove(request: HttpRequest, wedding, member_id) -> HttpResponse:
    capabilities = capability_flags(wedding, request.user)
    if not capabilities["manage_members"] and not capabilities["is_owner"]:
        raise Http404

    membership = get_object_or_404(WeddingMember, pk=member_id, wedding=wedding)
    if membership.user_id == wedding.owner_id:
        messages.error(request, "O proprietário não pode ser removido da equipa.")
        return redirect("weddings:team", wedding_id=wedding.pk)

    services.deactivate_member(membership=membership, actor=request.user, request=request)
    messages.info(request, "Acesso do membro revogado.")
    return redirect("weddings:team", wedding_id=wedding.pk)
