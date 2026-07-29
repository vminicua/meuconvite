from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

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
    """All weddings the user owns or helps to manage."""
    return render(
        request,
        "weddings/wedding_list.html",
        {
            "weddings": weddings_for_user(request.user),
            "archived": archived_weddings_for_user(request.user),
        },
    )


@login_required
def wedding_create(request: HttpRequest) -> HttpResponse:
    """Wizard step 1 — creates the wedding and its owner membership."""
    if request.method == "POST":
        form = WeddingCreateForm(request.POST)
        if form.is_valid():
            wedding = services.create_wedding(
                owner=request.user, data=form.cleaned_data, request=request
            )
            messages.success(
                request,
                "Casamento criado. Vamos agora configurar os eventos da celebração.",
            )
            return redirect("events:list", wedding_id=wedding.pk)
        messages.error(request, "Corrija os erros assinalados no formulário.")
    else:
        form = WeddingCreateForm()

    return render(request, "weddings/wedding_form.html", {"form": form, "step": 1})


# ---------------------------------------------------------------------
# Dashboard & settings
# ---------------------------------------------------------------------


@require_wedding()
def wedding_detail(request: HttpRequest, wedding) -> HttpResponse:
    """Wedding dashboard."""
    return render(
        request,
        "weddings/wedding_detail.html",
        {
            "wedding": wedding,
            "summary": dashboard_summary(wedding),
            "checklist": services.build_checklist(wedding),
            "events": upcoming_events(wedding),
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
            services.update_wedding(
                wedding=wedding,
                data=form.cleaned_data,
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

    return render(
        request,
        "weddings/wedding_design.html",
        {"wedding": wedding, "form": form, "capabilities": capability_flags(wedding, request.user)},
    )


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

    messages.success(request, "Casamento publicado. A página pública já está disponível.")
    return redirect("weddings:detail", wedding_id=wedding.pk)


@require_POST
@require_wedding()
def wedding_unpublish(request: HttpRequest, wedding) -> HttpResponse:
    if not user_can(wedding, request.user, "can_manage_events"):
        raise Http404
    services.unpublish_wedding(wedding=wedding, actor=request.user, request=request)
    messages.info(request, "Casamento despublicado. As páginas públicas deixaram de responder.")
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
    messages.info(request, "Casamento arquivado. Nenhum dado foi eliminado.")
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
