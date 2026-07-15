# Pix dinâmico (cob/cobv BACEN) — só providers REST; brcobrança não emite Pix.
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.vault import Vault, get_vault
from app.registry import build_rest_provider, credentials_from_header
from app.routers._credentials import resolve_request_credentials
from app.schemas import LoteCobvIn, PixCobrancaIn, PixCobrancaOut, Provider

router = APIRouter(prefix="/pix", tags=["pix"])

_CREDS_HEADER = Header(
    default=None,
    alias="X-Bank-Credentials",
    description="Credenciais do banco (JSON em base64) — só memória, nunca persistidas. Fallback: cofre VAULT__*.",
)
_AUTH_HEADER = Header(default=None, description="Bearer bapi_... (token do /credenciais)")


def _provider(tenant_id: str, provider: Provider, account_config: dict, vault: Vault,
              credentials: dict | None = None):
    try:
        return build_rest_provider(
            provider=provider, tenant_id=tenant_id, account_config=account_config,
            vault=vault, credentials=credentials,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("", response_model=PixCobrancaOut)
def criar(
    body: PixCobrancaIn,
    authorization: str | None = _AUTH_HEADER,
    vault: Vault = Depends(get_vault),
) -> PixCobrancaOut:
    """Cria cobrança Pix: cob imediata (default) ou cobv se `data_vencimento`."""
    creds = resolve_request_credentials(
        authorization=authorization, explicit=body.credentials,
        tenant_id=body.tenant_id, provider=body.provider,
    )
    p = _provider(body.tenant_id, body.provider, body.account_config, vault, creds)
    try:
        return p.criar_pix(body.pix)
    except ValueError as e:  # chave/txid/devedor ausentes → erro do chamador
        raise HTTPException(status_code=422, detail=str(e)) from e


def _creds(credentials, authorization, tenant_id, provider):
    try:
        explicit = credentials_from_header(credentials)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return resolve_request_credentials(
        authorization=authorization, explicit=explicit,
        tenant_id=tenant_id, provider=provider,
    )


@router.get("", response_model=dict)
def listar(
    tenant_id: str, inicio: str, fim: str,
    vencimento: bool = False, provider: Provider = Provider.c6,
    credentials: str | None = _CREDS_HEADER,
    authorization: str | None = _AUTH_HEADER,
    vault: Vault = Depends(get_vault),
) -> dict:
    """Lista cobranças do período (RFC3339). `vencimento=true` lista cobv."""
    p = _provider(tenant_id, provider, {}, vault,
                  _creds(credentials, authorization, tenant_id, provider))
    return p.listar_pix(inicio=inicio, fim=fim, vencimento=vencimento)


@router.get("/recebidos", response_model=dict)
def listar_recebidos(
    tenant_id: str, inicio: str, fim: str, provider: Provider = Provider.c6,
    credentials: str | None = _CREDS_HEADER,
    authorization: str | None = _AUTH_HEADER,
    vault: Vault = Depends(get_vault),
) -> dict:
    """Pix RECEBIDOS (money-in) no período — conciliação Pix (P_05 BACEN)."""
    p = _provider(tenant_id, provider, {}, vault,
                  _creds(credentials, authorization, tenant_id, provider))
    return p.listar_pix_recebidos(inicio=inicio, fim=fim)


@router.get("/recebidos/{e2eid}", response_model=dict)
def consultar_recebido(
    e2eid: str, tenant_id: str, provider: Provider = Provider.c6,
    credentials: str | None = _CREDS_HEADER,
    authorization: str | None = _AUTH_HEADER,
    vault: Vault = Depends(get_vault),
) -> dict:
    """Detalhe de um Pix RECEBIDO pelo e2eid (conciliação money-in)."""
    p = _provider(tenant_id, provider, {}, vault,
                  _creds(credentials, authorization, tenant_id, provider))
    return p.consultar_pix_recebido(e2eid)


@router.put("/recebidos/{e2eid}/devolucao/{devolucao_id}", response_model=dict, status_code=201)
def devolver(
    e2eid: str, devolucao_id: str, body: dict, tenant_id: str, provider: Provider = Provider.c6,
    credentials: str | None = _CREDS_HEADER,
    authorization: str | None = _AUTH_HEADER,
    vault: Vault = Depends(get_vault),
) -> dict:
    """Devolução (total/parcial) de um Pix recebido: corpo {"valor": "10.00"}."""
    if not body.get("valor"):
        raise HTTPException(status_code=422, detail="corpo deve conter valor")
    p = _provider(tenant_id, provider, {}, vault,
                  _creds(credentials, authorization, tenant_id, provider))
    return p.devolver_pix(e2eid, devolucao_id, str(body["valor"]))


@router.get("/recebidos/{e2eid}/devolucao/{devolucao_id}", response_model=dict)
def consultar_devolucao(
    e2eid: str, devolucao_id: str, tenant_id: str, provider: Provider = Provider.c6,
    credentials: str | None = _CREDS_HEADER,
    authorization: str | None = _AUTH_HEADER,
    vault: Vault = Depends(get_vault),
) -> dict:
    """Consulta uma devolução de Pix recebido."""
    p = _provider(tenant_id, provider, {}, vault,
                  _creds(credentials, authorization, tenant_id, provider))
    return p.consultar_devolucao(e2eid, devolucao_id)


@router.get("/lotes", response_model=dict)
def listar_lotes(
    tenant_id: str, inicio: str, fim: str, provider: Provider = Provider.c6,
    credentials: str | None = _CREDS_HEADER,
    authorization: str | None = _AUTH_HEADER,
    vault: Vault = Depends(get_vault),
) -> dict:
    """Lista lotes de cobv do período (RFC3339)."""
    p = _provider(tenant_id, provider, {}, vault,
                  _creds(credentials, authorization, tenant_id, provider))
    return p.listar_lotes_cobv(inicio=inicio, fim=fim)


@router.put("/lote/{lote_id}", response_model=dict)
def criar_lote(
    lote_id: str, body: LoteCobvIn,
    authorization: str | None = _AUTH_HEADER,
    vault: Vault = Depends(get_vault),
) -> dict:
    """Cria/atualiza lote de cobranças com vencimento (lotecobv BACEN)."""
    creds = resolve_request_credentials(
        authorization=authorization, explicit=body.credentials,
        tenant_id=body.tenant_id, provider=body.provider,
    )
    p = _provider(body.tenant_id, body.provider, body.account_config, vault, creds)
    from app.providers.c6 import _devedor  # mapeamento canonico -> BACEN
    chave_conta = body.account_config.get("chave_pix")
    cobsv = []
    for pix in body.cobrancas:
        if not (pix.txid and pix.data_vencimento and pix.devedor):
            raise HTTPException(status_code=422, detail="cada item do lote exige txid, data_vencimento e devedor")
        cobsv.append({
            "txid": pix.txid,
            "calendario": {"dataDeVencimento": pix.data_vencimento.isoformat(),
                           "validadeAposVencimento": pix.validade_apos_vencimento},
            "devedor": _devedor(pix.devedor),
            "valor": {"original": f"{pix.valor:.2f}"},
            "chave": pix.chave or chave_conta,
        })
    return p.criar_lote_cobv(lote_id, body.descricao, cobsv)


@router.get("/lote/{lote_id}", response_model=dict)
def consultar_lote(
    lote_id: str, tenant_id: str, provider: Provider = Provider.c6,
    credentials: str | None = _CREDS_HEADER,
    authorization: str | None = _AUTH_HEADER,
    vault: Vault = Depends(get_vault),
) -> dict:
    """Consulta um lote de cobv pelo id."""
    p = _provider(tenant_id, provider, {}, vault,
                  _creds(credentials, authorization, tenant_id, provider))
    return p.consultar_lote_cobv(lote_id)


@router.get("/{txid}", response_model=PixCobrancaOut)
def consultar(
    txid: str, tenant_id: str, vencimento: bool = False, provider: Provider = Provider.c6,
    credentials: str | None = _CREDS_HEADER,
    authorization: str | None = _AUTH_HEADER,
    vault: Vault = Depends(get_vault),
) -> PixCobrancaOut:
    """`vencimento=true` consulta cobv (/cobv/{txid}); default cob."""
    p = _provider(tenant_id, provider, {}, vault,
                  _creds(credentials, authorization, tenant_id, provider))
    return p.consultar_pix(txid, vencimento=vencimento)


@router.patch("/{txid}", response_model=PixCobrancaOut)
def revisar(
    txid: str, campos: dict, tenant_id: str,
    vencimento: bool = False, provider: Provider = Provider.c6,
    credentials: str | None = _CREDS_HEADER,
    authorization: str | None = _AUTH_HEADER,
    vault: Vault = Depends(get_vault),
) -> PixCobrancaOut:
    """Revisa a cobrança (PATCH BACEN): valor, solicitacaoPagador, calendario..."""
    p = _provider(tenant_id, provider, {}, vault,
                  _creds(credentials, authorization, tenant_id, provider))
    return p.revisar_pix(txid, campos, vencimento=vencimento)
