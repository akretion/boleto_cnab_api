# Conciliação online (C6 Pay statement) — recebíveis e transações por período.
#
# Períodos de até 60 dias por requisição (limite da API do C6).
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.core.vault import Vault, get_vault
from app.registry import build_rest_provider, credentials_from_header
from app.routers._credentials import resolve_request_credentials
from app.schemas import ConciliacaoOut, Provider

router = APIRouter(prefix="/conciliacao", tags=["conciliacao"])

_CREDS_HEADER = Header(
    default=None,
    alias="X-Bank-Credentials",
    description="Credenciais do banco (JSON em base64) — só memória, nunca persistidas. Fallback: cofre VAULT__*.",
)
_AUTH_HEADER = Header(default=None, description="Bearer bapi_... (token do /credenciais)")


def _provider(tenant_id: str, provider: Provider, vault: Vault,
              credentials_header: str | None, authorization: str | None):
    try:
        explicit = credentials_from_header(credentials_header)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    creds = resolve_request_credentials(
        authorization=authorization, explicit=explicit,
        tenant_id=tenant_id, provider=provider,
    )
    try:
        return build_rest_provider(
            provider=provider, tenant_id=tenant_id, account_config={}, vault=vault,
            credentials=creds,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/recebiveis", response_model=ConciliacaoOut)
def recebiveis(
    tenant_id: str,
    start_date: str = Query(description="Data inicial (YYYY-MM-DD)"),
    end_date: str = Query(description="Data final (YYYY-MM-DD, máx. 60 dias após start)"),
    provider: Provider = Provider.c6,
    page: int = 1,
    size: int = Query(default=50, le=100),
    credentials: str | None = _CREDS_HEADER,
    authorization: str | None = _AUTH_HEADER,
    vault: Vault = Depends(get_vault),
) -> ConciliacaoOut:
    """Recebíveis C6 Pay do período (paginado; máx. 60 dias por consulta)."""
    p = _provider(tenant_id, provider, vault, credentials, authorization)
    return p.listar_recebiveis(start_date=start_date, end_date=end_date, page=page, size=size)


@router.get("/transacoes", response_model=ConciliacaoOut)
def transacoes(
    tenant_id: str,
    start_date: str = Query(description="Data inicial (YYYY-MM-DD)"),
    end_date: str = Query(description="Data final (YYYY-MM-DD, máx. 60 dias após start)"),
    provider: Provider = Provider.c6,
    page: int = 1,
    size: int = Query(default=50, le=100),
    credentials: str | None = _CREDS_HEADER,
    authorization: str | None = _AUTH_HEADER,
    vault: Vault = Depends(get_vault),
) -> ConciliacaoOut:
    """Transações C6 Pay do período (paginado; máx. 60 dias por consulta)."""
    p = _provider(tenant_id, provider, vault, credentials, authorization)
    return p.listar_transacoes(start_date=start_date, end_date=end_date, page=page, size=size)
