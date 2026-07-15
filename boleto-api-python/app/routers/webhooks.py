from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, HTTPException, Request

from app.core.forwarder import forward_event
from app.core.subscriptions import resolve_callback
from app.providers.c6 import C6Provider
from app.providers.sicoob import SicoobProvider
from app.schemas import WebhookEvent

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_NORMALIZERS = {"c6": C6Provider, "sicoob": SicoobProvider}


def _check_token(banco: str, request: Request) -> None:
    """Autenticidade do webhook por token de rota (query `?token=` ou header
    `x-webhook-token`), comparado em tempo constante.

    Os bancos (C6 incluso) não documentam assinatura no payload; o padrão de
    mercado é embutir um segredo na URL cadastrada no banco. Opt-in por env
    `WEBHOOK_TOKEN__<BANCO>` — sem a env, aceita (compatível com o comportamento
    anterior). TODO homologação: trocar por assinatura se o banco oferecer.
    """
    expected = os.environ.get(f"WEBHOOK_TOKEN__{banco.upper()}", "")
    if not expected:
        return
    got = request.query_params.get("token") or request.headers.get("x-webhook-token", "")
    if not hmac.compare_digest(got, expected):
        raise HTTPException(status_code=401, detail="webhook token inválido")


async def _handle(banco: str, request: Request, tenant_id: str | None) -> WebhookEvent:
    _check_token(banco, request)
    body = await request.json()
    klass = _NORMALIZERS.get(banco)
    if not klass:
        return WebhookEvent(event="ignorado", raw={"banco": banco})

    event = klass(account_config={}, credentials={}).normalizar_webhook(dict(request.headers), body)

    # Push assinado (HMAC) ao consumidor DONO do tenant (multi-sistema). Sem
    # tenant na rota, cai no destino global. forward_event no-op se não houver destino.
    cb = resolve_callback(tenant_id)
    forward_event(event.model_dump(), url=cb[0] if cb else None, secret=cb[1] if cb else None)
    return event


@router.post("/{banco}", response_model=WebhookEvent)
async def receber(banco: str, request: Request) -> WebhookEvent:
    """Webhook global (consumidor único / destino default)."""
    return await _handle(banco, request, tenant_id=None)


@router.post("/{banco}/{tenant_id}", response_model=WebhookEvent)
async def receber_por_tenant(banco: str, tenant_id: str, request: Request) -> WebhookEvent:
    """Webhook por tenant (multi-sistema). O banco aponta o callback de cada conta
    para esta URL; o tenant vem do path e roteia para o consumidor dono."""
    return await _handle(banco, request, tenant_id=tenant_id)
