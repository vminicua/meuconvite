from __future__ import annotations

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET


def home(request: HttpRequest) -> HttpResponse:
    """Public landing page. Authenticated users go straight to their weddings."""
    if request.user.is_authenticated:
        return redirect("weddings:list")
    return render(request, "core/home.html")


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    """
    Lightweight liveness probe.

    Only reports that the process is up and the database answers; no
    version or configuration detail is exposed.
    """
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # pragma: no cover - depends on infrastructure
        return JsonResponse({"status": "degraded"}, status=503)
    return JsonResponse({"status": "ok"})
