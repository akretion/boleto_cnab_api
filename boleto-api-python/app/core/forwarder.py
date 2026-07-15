# Push de eventos normalizados para um CONSUMIDOR downstream (qualquer projeto).
#
# O Boleto-API é um produto standalone: cada sistema consumidor registra um webhook e recebe o evento normalizado via POST assinado
# (HMAC-SHA256), validável de forma timing-safe (hmac.compare_digest).
#
# Esquema de assinatura (o consumidor valida igual):
#   header  X-Signature: sha256=<hex(hmac_sha256(secret, raw_body))>
#   body    JSON compacto (separators sem espaço), UTF-8
#
# Destino: por padrão um webhook global (EVENT_WEBHOOK_URL / EVENT_WEBHOOK_SECRET),
# mas forward_event aceita override por chamada — base para callback por tenant
# (multi-consumidor) quando o mapeamento webhook->tenant estiver pronto.
from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any

import httpx


def sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def forward_event(event: dict[str, Any], *, url: str | None = None, secret: str | None = None) -> bool:
    """Encaminha o evento ao consumidor downstream. True se entregue (2xx/3xx).

    `url`/`secret` permitem override por chamada (ex.: callback por tenant),
    caindo no global EVENT_WEBHOOK_URL / EVENT_WEBHOOK_SECRET. No-op (False) se
    não houver destino — o webhook do banco não pode falhar por causa do push.
    """
    url = url or os.environ.get("EVENT_WEBHOOK_URL", "")
    if not url:
        return False

    secret = secret if secret is not None else os.environ.get("EVENT_WEBHOOK_SECRET", "")
    body = json.dumps(event, default=str, separators=(",", ":")).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Signature"] = sign(body, secret)

    try:
        with httpx.Client(timeout=10.0) as c:
            r = c.post(url, content=body, headers=headers)
            return r.status_code < 400
    except httpx.HTTPError:
        # TODO: enfileirar para retry (o webhook do banco não pode quebrar aqui).
        return False
