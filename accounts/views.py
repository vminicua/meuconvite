from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from audit.services import log_update, model_to_dict

from .forms import ProfileForm


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    """View and edit the signed-in user's own profile."""
    user = request.user

    if request.method == "POST":
        old_data = model_to_dict(user)
        form = ProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            log_update(user, old_data=old_data, actor=user, request=request)
            messages.success(request, "Perfil actualizado com sucesso.")
            return redirect("accounts:profile")
        messages.error(request, "Corrija os erros assinalados no formulário.")
    else:
        form = ProfileForm(instance=user)

    return render(request, "accounts/profile.html", {"form": form})
