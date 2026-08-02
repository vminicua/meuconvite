"""Cliente mínimo e estrito para a API oficial da Payzeno."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


class PayzenoError(Exception):
    """Erro seguro para apresentar à aplicação, sem expor segredos."""


class PayzenoConfigurationError(PayzenoError):
    pass


class PayzenoAPIError(PayzenoError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class PayzenoClient:
    api_key: str
    base_url: str = "https://api.payzeno.io"
    timeout: int = 20

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme != "https" or parsed.hostname != "api.payzeno.io":
            raise PayzenoConfigurationError(
                "A API tem de usar o endereço oficial https://api.payzeno.io."
            )
        if not self.api_key.strip():
            raise PayzenoConfigurationError("A chave da API Payzeno não está configurada.")

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict | None = None,
        idempotency_key: str = "",
    ) -> dict:
        headers = {"Accept": "application/json", "Api-Key": self.api_key.strip()}
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key[:128]
        request = Request(
            urljoin(self.base_url.rstrip("/") + "/", path.lstrip("/")),
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read(1024 * 1024)
        except HTTPError as exc:
            # O corpo pode conter detalhes úteis para logs internos, mas nunca
            # deve chegar ao utilizador nem ser persistido com dados sensíveis.
            raise PayzenoAPIError(
                "A Payzeno recusou o pedido de pagamento.", status_code=exc.code
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise PayzenoAPIError("Não foi possível contactar a Payzeno.") from exc
        try:
            result = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PayzenoAPIError("A Payzeno devolveu uma resposta inválida.") from exc
        if not isinstance(result, dict):
            raise PayzenoAPIError("A Payzeno devolveu uma resposta inválida.")
        return result

    def create_checkout(self, payload: dict, *, idempotency_key: str) -> dict:
        return self._request(
            "POST",
            "/v1/checkout/sessions",
            payload=payload,
            idempotency_key=idempotency_key,
        )

    def checkout_status(self, checkout_id: str) -> dict:
        if not checkout_id:
            raise PayzenoAPIError("O checkout Payzeno não foi criado.")
        return self._request("GET", f"/v1/checkout/sessions/{checkout_id}/status")


def response_data(response: dict) -> dict:
    """Aceita tanto respostas directas como envelopes ``data``."""
    nested = response.get("data")
    return nested if isinstance(nested, dict) else response
