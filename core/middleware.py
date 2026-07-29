"""Request scoped context, used by the audit trail."""

from __future__ import annotations

import threading
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

_local = threading.local()


def get_current_request() -> HttpRequest | None:
    """Current request, when running inside the request/response cycle."""
    return getattr(_local, "request", None)


class RequestContextMiddleware:
    """
    Stores the active request in a thread local.

    This is only used to enrich audit records (IP, user agent, actor) when
    a service is called far from the view. Business logic never depends on
    it: every service also accepts an explicit `actor`/`request` argument.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        _local.request = request
        try:
            return self.get_response(request)
        finally:
            _local.request = None
