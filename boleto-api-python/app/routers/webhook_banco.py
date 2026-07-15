# Cadastro do webhook NO BANCO (C6 /v1/webhooks) — o banco passa a notificar a
# URL informada (ex.: a rota /webhooks/{banco}/{tenant} deste gateway).
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.vault import Vault, get_vault
from app.registry import build_rest_provider, credentials_from_header
from app.routers._credentials import resolve_request_credentials
from app.schemas import Provider, WebhookBancoIn

router = APIRouter(prefix="/config/webhook-banco", tags=["config"])

_CREDS_HEADER = Header(default=None, alias="X-Bank-Credentials",
                       description="Credenciais do banco (JSON base64) — só memória.")
_AUTH_HEADER = Header(default=None, description="Bearer bapi_... (token do /credenciais)")


def _provider(tenant_id, provider, vault, credentials):
    try:
        return build_rest_provider(provider=provider, tenant_id=tenant_id,
                                   account_config={}, vault=vault, credentials=credentials)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("", response_model=dict)
def cadastrar(body: WebhookBancoIn, authorization: str | None = _AUTH_HEADER,
              vault: Vault = Depends(get_vault)) -> dict:
    """Registra a URL de notificação no banco (service: BANK_SLIP | CHECKOUT)."""
    creds = resolve_request_credentials(authorization=authorization, explicit=body.credentials,
                                        tenant_id=body.tenant_id, provider=body.provider)
    p = _provider(body.tenant_id, body.provider, vault, creds)
    return p.cadastrar_webhook(url=body.url, service=body.service)


@router.get("", response_model=dict)
def consultar(tenant_id: str, service: str = "BANK_SLIP", provider: Provider = Provider.c6,
              credentials: str | None = _CREDS_HEADER,
              authorization: str | None = _AUTH_HEADER,
              vault: Vault = Depends(get_vault)) -> dict:
    """Consulta o webhook cadastrado no banco para o service."""
    try:
        explicit = credentials_from_header(credentials)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    creds = resolve_request_credentials(authorization=authorization, explicit=explicit,
                                        tenant_id=tenant_id, provider=provider)
    return _provider(tenant_id, provider, vault, creds).consultar_webhook(service=service)


@router.delete("", response_model=dict)
def remover(tenant_id: str, service: str = "BANK_SLIP", provider: Provider = Provider.c6,
            credentials: str | None = _CREDS_HEADER,
            authorization: str | None = _AUTH_HEADER,
            vault: Vault = Depends(get_vault)) -> dict:
    """Remove o webhook do service no banco."""
    try:
        explicit = credentials_from_header(credentials)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    creds = resolve_request_credentials(authorization=authorization, explicit=explicit,
                                        tenant_id=tenant_id, provider=provider)
    return _provider(tenant_id, provider, vault, creds).remover_webhook(service=service)


# --- webhook Pix BACEN por CHAVE (P_06) — banco chama a URL quando o Pix cai -----

pix_router = APIRouter(prefix="/config/webhook-pix", tags=["config"])


@pix_router.put("", response_model=dict)
def configurar_pix(body: dict, authorization: str | None = _AUTH_HEADER,
                   vault: Vault = Depends(get_vault)) -> dict:
    """Configura o webhook BACEN da chave: {tenant_id, provider?, chave, url, credentials?}."""
    for campo in ("tenant_id", "chave", "url"):
        if not body.get(campo):
            raise HTTPException(status_code=422, detail=f"campo obrigatório: {campo}")
    provider = Provider(body.get("provider") or "c6")
    creds = resolve_request_credentials(authorization=authorization,
                                        explicit=body.get("credentials"),
                                        tenant_id=body["tenant_id"], provider=provider)
    p = _provider(body["tenant_id"], provider, vault, creds)
    return p.configurar_webhook_pix(body["chave"], body["url"])


@pix_router.get("", response_model=dict)
def consultar_pix(tenant_id: str, chave: str, provider: Provider = Provider.c6,
                  credentials: str | None = _CREDS_HEADER,
                  authorization: str | None = _AUTH_HEADER,
                  vault: Vault = Depends(get_vault)) -> dict:
    """Consulta o webhook BACEN cadastrado para a chave Pix."""
    try:
        explicit = credentials_from_header(credentials)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    creds = resolve_request_credentials(authorization=authorization, explicit=explicit,
                                        tenant_id=tenant_id, provider=provider)
    return _provider(tenant_id, provider, vault, creds).consultar_webhook_pix(chave)


@pix_router.delete("", response_model=dict)
def remover_pix(tenant_id: str, chave: str, provider: Provider = Provider.c6,
                credentials: str | None = _CREDS_HEADER,
                authorization: str | None = _AUTH_HEADER,
                vault: Vault = Depends(get_vault)) -> dict:
    """Remove o webhook BACEN da chave Pix."""
    try:
        explicit = credentials_from_header(credentials)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    creds = resolve_request_credentials(authorization=authorization, explicit=explicit,
                                        tenant_id=tenant_id, provider=provider)
    return _provider(tenant_id, provider, vault, creds).remover_webhook_pix(chave)
