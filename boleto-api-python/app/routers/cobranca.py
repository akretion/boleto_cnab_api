from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.vault import Vault, get_vault
from app.registry import build_provider, credentials_from_header
from app.routers._credentials import resolve_request_credentials
from app.schemas import CobrancaIn, CobrancaOut, Provider

router = APIRouter(prefix="/cobranca", tags=["cobranca"])

_CREDS_HEADER = Header(
    default=None,
    alias="X-Bank-Credentials",
    description="Credenciais do banco (JSON em base64) — só memória, nunca persistidas. Fallback: cofre VAULT__*.",
)
_AUTH_HEADER = Header(default=None, description="Bearer bapi_... (token do /credenciais)")


def _header_creds(value: str | None) -> dict | None:
    try:
        return credentials_from_header(value)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("", response_model=CobrancaOut)
def registrar(
    body: CobrancaIn,
    authorization: str | None = _AUTH_HEADER,
    vault: Vault = Depends(get_vault),
) -> CobrancaOut:
    """Registra a cobrança (boleto): `provider=c6|sicoob` = API REST do banco;
    vazio/omitido = CNAB offline (engine Ruby). Resposta normalizada."""
    creds = resolve_request_credentials(
        authorization=authorization, explicit=body.credentials,
        tenant_id=body.tenant_id, provider=body.provider,
    )
    provider = build_provider(
        provider=body.provider, tenant_id=body.tenant_id,
        account_config=body.account_config, vault=vault, credentials=creds,
    )
    return provider.registrar(body.cobranca)


@router.get("/{cobranca_id}", response_model=CobrancaOut)
def consultar(
    cobranca_id: str, tenant_id: str, provider: Provider,
    credentials: str | None = _CREDS_HEADER,
    authorization: str | None = _AUTH_HEADER,
    vault: Vault = Depends(get_vault),
) -> CobrancaOut:
    """Consulta o status normalizado do boleto (registrado|pendente|liquidado|baixado)."""
    creds = resolve_request_credentials(
        authorization=authorization, explicit=_header_creds(credentials),
        tenant_id=tenant_id, provider=provider,
    )
    p = build_provider(provider=provider, tenant_id=tenant_id, account_config={},
                       vault=vault, credentials=creds)
    return p.consultar(cobranca_id)


@router.get("/{cobranca_id}/pdf", response_model=CobrancaOut)
def pdf(
    cobranca_id: str, tenant_id: str, provider: Provider,
    credentials: str | None = _CREDS_HEADER,
    authorization: str | None = _AUTH_HEADER,
    vault: Vault = Depends(get_vault),
) -> CobrancaOut:
    """PDF do boleto registrado (quando o banco fornece; C6 devolve base64)."""
    creds = resolve_request_credentials(
        authorization=authorization, explicit=_header_creds(credentials),
        tenant_id=tenant_id, provider=provider,
    )
    p = build_provider(provider=provider, tenant_id=tenant_id, account_config={},
                       vault=vault, credentials=creds)
    try:
        return p.pdf(cobranca_id)
    except NotImplementedError as e:
        raise HTTPException(status_code=422, detail="provider não fornece PDF online") from e


@router.put("/{cobranca_id}", response_model=CobrancaOut)
def alterar(
    cobranca_id: str, campos: dict, tenant_id: str, provider: Provider,
    credentials: str | None = _CREDS_HEADER,
    authorization: str | None = _AUTH_HEADER,
    vault: Vault = Depends(get_vault),
) -> CobrancaOut:
    """Altera boleto emitido (amount, due_date, discount, interest, fine)."""
    creds = resolve_request_credentials(
        authorization=authorization, explicit=_header_creds(credentials),
        tenant_id=tenant_id, provider=provider,
    )
    p = build_provider(provider=provider, tenant_id=tenant_id, account_config={},
                       vault=vault, credentials=creds)
    try:
        return p.alterar(cobranca_id, campos)
    except NotImplementedError as e:
        raise HTTPException(status_code=422, detail="provider não suporta alteração online") from e


@router.delete("/{cobranca_id}", response_model=CobrancaOut)
def baixar(
    cobranca_id: str, tenant_id: str, provider: Provider,
    credentials: str | None = _CREDS_HEADER,
    authorization: str | None = _AUTH_HEADER,
    vault: Vault = Depends(get_vault),
) -> CobrancaOut:
    """Baixa/cancela o boleto (409 enquanto a CIP processa o registro)."""
    creds = resolve_request_credentials(
        authorization=authorization, explicit=_header_creds(credentials),
        tenant_id=tenant_id, provider=provider,
    )
    p = build_provider(provider=provider, tenant_id=tenant_id, account_config={},
                       vault=vault, credentials=creds)
    return p.baixar(cobranca_id)
