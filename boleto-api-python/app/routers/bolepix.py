# Bolepix — boleto híbrido online com Pix EVP (C6 /v2/bank_slips).
#
# Schema do v2 difere do boleto v1: external_reference_id ^[A-Z0-9]{26}$ e
# address do pagador unificado (rua+número num campo) + neighborhood.
from __future__ import annotations

import random
import string

from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.vault import Vault, get_vault
from app.registry import build_rest_provider, credentials_from_header
from app.routers._credentials import resolve_request_credentials
from app.schemas import BolepixIn, CobrancaOut, Pagador, Provider

router = APIRouter(prefix="/bolepix", tags=["bolepix"])

_CREDS_HEADER = Header(default=None, alias="X-Bank-Credentials",
                       description="Credenciais do banco (JSON base64) — só memória.")
_AUTH_HEADER = Header(default=None, description="Bearer bapi_... (token do /credenciais)")


def _provider(tenant_id, provider, account_config, vault, credentials):
    try:
        return build_rest_provider(provider=provider, tenant_id=tenant_id,
                                   account_config=account_config, vault=vault,
                                   credentials=credentials)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


def _payer_v2(pagador: Pagador) -> dict:
    end = pagador.endereco or {}
    linha = end.get("address")
    if not linha:
        rua = end.get("street") or end.get("logradouro") or ""
        num = end.get("number") or end.get("numero")
        linha = f"{rua}, {num}" if num else rua
    address = {
        "address": linha,
        "neighborhood": end.get("neighborhood") or end.get("bairro"),
        "city": end.get("city") or end.get("cidade"),
        "state": end.get("state") or end.get("uf"),
        "zip_code": end.get("zip_code") or end.get("cep"),
    }
    payer = {"name": pagador.nome, "tax_id": pagador.documento,
             "address": {k: v for k, v in address.items() if v is not None}}
    if end.get("email"):
        payer["email"] = end["email"]
    return payer


def _novo_ext_ref() -> str:
    return "".join(random.SystemRandom().choices(string.ascii_uppercase + string.digits, k=26))


@router.post("", response_model=CobrancaOut, status_code=201)
def criar(body: BolepixIn, authorization: str | None = _AUTH_HEADER,
          vault: Vault = Depends(get_vault)) -> CobrancaOut:
    """Emite Bolepix (boleto + QR Pix EVP). Reenvio com o mesmo
    external_reference_id devolve a cobrança existente (idempotente no banco)."""
    creds = resolve_request_credentials(authorization=authorization, explicit=body.credentials,
                                        tenant_id=body.tenant_id, provider=body.provider)
    p = _provider(body.tenant_id, body.provider, body.account_config, vault, creds)
    bp = body.bolepix
    chave = bp.chave_pix or body.account_config.get("chave_pix")
    dados = {
        "external_reference_id": bp.external_reference_id or _novo_ext_ref(),
        "amount": float(bp.valor),
        "due_date": bp.vencimento.isoformat(),
        "description": bp.descricao,
        "payer": _payer_v2(bp.pagador),
        "payment_method": {
            "bank_slip": {
                k: v for k, v in {
                    "billing_scheme": body.account_config.get("billing_scheme"),
                    "our_number": bp.nosso_numero,
                    "instructions": bp.instrucoes,
                }.items() if v is not None
            },
        },
    }
    if not dados["payment_method"]["bank_slip"].get("billing_scheme"):
        from app.providers.c6 import C6_BILLING_SCHEME
        dados["payment_method"]["bank_slip"]["billing_scheme"] = C6_BILLING_SCHEME
    if bp.dias_apos_vencimento is not None:
        dados["days_after_due_date"] = bp.dias_apos_vencimento
    if chave:  # sem chave, o banco emite boleto sem o segmento Pix
        dados["payment_method"]["pix"] = {"key": chave, "type": "EVP"}
    return p.criar_bolepix(dados)


@router.get("/{external_reference_id}", response_model=CobrancaOut)
def consultar(external_reference_id: str, tenant_id: str, provider: Provider = Provider.c6,
              credentials: str | None = _CREDS_HEADER,
              authorization: str | None = _AUTH_HEADER,
              vault: Vault = Depends(get_vault)) -> CobrancaOut:
    """Consulta o Bolepix pelo external_reference_id (26 chars A-Z0-9)."""
    try:
        explicit = credentials_from_header(credentials)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    creds = resolve_request_credentials(authorization=authorization, explicit=explicit,
                                        tenant_id=tenant_id, provider=provider)
    return _provider(tenant_id, provider, {}, vault, creds).consultar_bolepix(external_reference_id)


@router.get("/{external_reference_id}/pdf", response_model=CobrancaOut)
def pdf(external_reference_id: str, tenant_id: str, provider: Provider = Provider.c6,
        credentials: str | None = _CREDS_HEADER,
        authorization: str | None = _AUTH_HEADER,
        vault: Vault = Depends(get_vault)) -> CobrancaOut:
    """PDF do Bolepix em base64."""
    try:
        explicit = credentials_from_header(credentials)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    creds = resolve_request_credentials(authorization=authorization, explicit=explicit,
                                        tenant_id=tenant_id, provider=provider)
    return _provider(tenant_id, provider, {}, vault, creds).pdf_bolepix(external_reference_id)


@router.delete("/{external_reference_id}", response_model=CobrancaOut)
def cancelar(external_reference_id: str, tenant_id: str, provider: Provider = Provider.c6,
             credentials: str | None = _CREDS_HEADER,
             authorization: str | None = _AUTH_HEADER,
             vault: Vault = Depends(get_vault)) -> CobrancaOut:
    """Cancela o Bolepix (409 enquanto a CIP processa o registro)."""
    try:
        explicit = credentials_from_header(credentials)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    creds = resolve_request_credentials(authorization=authorization, explicit=explicit,
                                        tenant_id=tenant_id, provider=provider)
    return _provider(tenant_id, provider, {}, vault, creds).cancelar_bolepix(external_reference_id)
