# Extrato da conta PJ (C6 /v1/statement) — movimentações do período.
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.core.vault import Vault, get_vault
from app.registry import build_rest_provider, credentials_from_header
from app.routers._credentials import resolve_request_credentials
from app.schemas import Provider

router = APIRouter(prefix="/extrato", tags=["extrato"])

_CREDS_HEADER = Header(default=None, alias="X-Bank-Credentials",
                       description="Credenciais do banco (JSON base64) — só memória.")
_AUTH_HEADER = Header(default=None, description="Bearer bapi_... (token do /credenciais)")


@router.get("", response_model=dict)
def consultar(
    tenant_id: str,
    start_date: str = Query(description="Data inicial (YYYY-MM-DD)"),
    end_date: str = Query(description="Data final (YYYY-MM-DD)"),
    provider: Provider = Provider.c6,
    credentials: str | None = _CREDS_HEADER,
    authorization: str | None = _AUTH_HEADER,
    vault: Vault = Depends(get_vault),
) -> dict:
    """Extrato de movimentações da conta (exclusivo PJ no C6)."""
    try:
        explicit = credentials_from_header(credentials)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    creds = resolve_request_credentials(authorization=authorization, explicit=explicit,
                                        tenant_id=tenant_id, provider=provider)
    try:
        p = build_rest_provider(provider=provider, tenant_id=tenant_id,
                                account_config={}, vault=vault, credentials=creds)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    try:
        return p.extrato(start_date=start_date, end_date=end_date)
    except ValueError as e:  # ex.: extrato Sicoob multi-mês
        raise HTTPException(status_code=422, detail=str(e)) from e
