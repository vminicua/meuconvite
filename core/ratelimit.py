"""
Cache backed rate limiting for public endpoints.

Deliberately dependency free: it works with LocMemCache (single process,
typical on shared cPanel hosting) and with Redis when available. It is a
throttle, not a security boundary — authorisation is always enforced
separately.
"""

from __future__ import annotations

import functools
import hashlib
from collections.abc import Callable

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from .utils import get_client_ip


def _bucket_key(scope: str, identifier: str) -> str:
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:24]
    return f"ratelimit:{scope}:{digest}"


def is_rate_limited(scope: str, identifier: str, limit: int, window_seconds: int) -> bool:
    """Increment the counter for `identifier` and report whether it exceeded `limit`."""
    key = _bucket_key(scope, identifier)
    added = cache.add(key, 1, window_seconds)
    if added:
        return False
    try:
        count = cache.incr(key)
    except ValueError:  # entry expired between add() and incr()
        cache.set(key, 1, window_seconds)
        return False
    return count > limit


def rate_limit(
    scope: str,
    limit: int | None = None,
    window_seconds: int | None = None,
    key_func: Callable[[HttpRequest], str] | None = None,
    methods: tuple[str, ...] = ("POST",),
) -> Callable:
    """
    View decorator.

    Defaults are read from `settings.PUBLIC_RATE_LIMITS[scope]`, so limits
    can be tuned per environment without touching the views.
    """

    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            if methods and request.method not in methods:
                return view_func(request, *args, **kwargs)

            configured = getattr(settings, "PUBLIC_RATE_LIMITS", {}).get(scope)
            effective_limit = limit or (configured[0] if configured else 60)
            effective_window = window_seconds or (configured[1] if configured else 3600)

            identifier = key_func(request) if key_func else (get_client_ip(request) or "anon")
            if is_rate_limited(scope, identifier, effective_limit, effective_window):
                from django.shortcuts import render

                return render(
                    request,
                    "core/rate_limited.html",
                    {
                        "message": _(
                            "Foram feitos demasiados pedidos a partir desta ligação. "
                            "Aguarde alguns minutos e tente novamente."
                        )
                    },
                    status=429,
                )
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
