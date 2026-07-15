# Pix Automático (BACEN) — débito recorrente autorizado uma vez pelo pagador.
#
# O AGENDAMENTO de cada cobrança do ciclo (>= 2 dias antes do vencimento) fica
# no PRODUTO consumidor — este gateway é interface de consumo (stateless).
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.vault import Vault, get_vault
from app.providers.bacen_pix import _devedor_simples
from app.registry import build_rest_provider, credentials_from_header
from app.routers._credentials import resolve_request_credentials
from app.schemas import (
    CobrancaRecorrenteIn,
    Provider,
    RecorrenciaIn,
    SolicitacaoRecorrenciaIn,
)

router = APIRouter(prefix="/pix-automatico", tags=["pix-automatico"])

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


def _creds_get(credentials, authorization, tenant_id, provider):
    try:
        explicit = credentials_from_header(credentials)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return resolve_request_credentials(authorization=authorization, explicit=explicit,
                                       tenant_id=tenant_id, provider=provider)


# --- recorrências ------------------------------------------------------------------


@router.post("/recorrencias", response_model=dict, status_code=201)
def criar_recorrencia(body: RecorrenciaIn, authorization: str | None = _AUTH_HEADER,
                      vault: Vault = Depends(get_vault)) -> dict:
    """Cria a recorrência (rec). O pagador autoriza via app (solicrec) ou QR (loc)."""
    rec = body.recorrencia
    if bool(rec.valor_fixo) == bool(rec.valor_minimo):
        raise HTTPException(status_code=422,
                            detail="informe exatamente um: valor_fixo (valorRec) ou valor_minimo")
    creds = resolve_request_credentials(authorization=authorization, explicit=body.credentials,
                                        tenant_id=body.tenant_id, provider=body.provider)
    p = _provider(body.tenant_id, body.provider, body.account_config, vault, creds)

    vinculo = {"contrato": rec.contrato, "devedor": _devedor_simples(rec.devedor)}
    if rec.objeto:
        vinculo["objeto"] = rec.objeto
    calendario = {"dataInicial": rec.data_inicial.isoformat(), "periodicidade": rec.periodicidade}
    if rec.data_final:
        calendario["dataFinal"] = rec.data_final.isoformat()
    valor = ({"valorRec": f"{rec.valor_fixo:.2f}"} if rec.valor_fixo
             else {"valorMinimoRecebedor": f"{rec.valor_minimo:.2f}"})
    payload = {"vinculo": vinculo, "calendario": calendario, "valor": valor,
               "politicaRetentativa": rec.politica_retentativa}
    if rec.loc is not None:
        payload["loc"] = rec.loc
    if rec.txid_ativacao:
        payload["ativacao"] = {"dadosJornada": {"txid": rec.txid_ativacao}}
    if rec.extras:
        payload.update(rec.extras)
    return p.criar_recorrencia(payload)


@router.get("/recorrencias", response_model=dict)
def listar_recorrencias(tenant_id: str, inicio: str, fim: str, provider: Provider = Provider.c6,
                        credentials: str | None = _CREDS_HEADER,
                        authorization: str | None = _AUTH_HEADER,
                        vault: Vault = Depends(get_vault)) -> dict:
    """Lista recorrências do período (RFC3339)."""
    creds = _creds_get(credentials, authorization, tenant_id, provider)
    return _provider(tenant_id, provider, {}, vault, creds).listar_recorrencias(inicio=inicio, fim=fim)


@router.get("/recorrencias/{id_rec}", response_model=dict)
def consultar_recorrencia(id_rec: str, tenant_id: str, txid: str | None = None,
                          provider: Provider = Provider.c6,
                          credentials: str | None = _CREDS_HEADER,
                          authorization: str | None = _AUTH_HEADER,
                          vault: Vault = Depends(get_vault)) -> dict:
    """Consulta a recorrência (opcionalmente por txid da jornada)."""
    creds = _creds_get(credentials, authorization, tenant_id, provider)
    return _provider(tenant_id, provider, {}, vault, creds).consultar_recorrencia(id_rec, txid=txid)


@router.patch("/recorrencias/{id_rec}", response_model=dict)
def revisar_recorrencia(id_rec: str, campos: dict, tenant_id: str,
                        provider: Provider = Provider.c6,
                        credentials: str | None = _CREDS_HEADER,
                        authorization: str | None = _AUTH_HEADER,
                        vault: Vault = Depends(get_vault)) -> dict:
    """Gestão (Jornada 4): alteração ou cancelamento (ex.: {"status": "CANCELADA"})."""
    creds = _creds_get(credentials, authorization, tenant_id, provider)
    return _provider(tenant_id, provider, {}, vault, creds).revisar_recorrencia(id_rec, campos)


# --- solicitação de confirmação (Jornada 1) ------------------------------------------


@router.post("/solicitacoes", response_model=dict, status_code=201)
def criar_solicitacao(body: SolicitacaoRecorrenciaIn, authorization: str | None = _AUTH_HEADER,
                      vault: Vault = Depends(get_vault)) -> dict:
    """solicrec: envia o pedido de autorização ao app do banco do pagador (Jornada 1)."""
    creds = resolve_request_credentials(authorization=authorization, explicit=body.credentials,
                                        tenant_id=body.tenant_id, provider=body.provider)
    p = _provider(body.tenant_id, body.provider, body.account_config, vault, creds)
    return p.criar_solicitacao_recorrencia(body.dados)


@router.get("/solicitacoes/{id_solic}", response_model=dict)
def consultar_solicitacao(id_solic: str, tenant_id: str, provider: Provider = Provider.c6,
                          credentials: str | None = _CREDS_HEADER,
                          authorization: str | None = _AUTH_HEADER,
                          vault: Vault = Depends(get_vault)) -> dict:
    """Consulta a solicitação de autorização."""
    creds = _creds_get(credentials, authorization, tenant_id, provider)
    return _provider(tenant_id, provider, {}, vault, creds).consultar_solicitacao_recorrencia(id_solic)


@router.patch("/solicitacoes/{id_solic}", response_model=dict)
def revisar_solicitacao(id_solic: str, campos: dict, tenant_id: str,
                        provider: Provider = Provider.c6,
                        credentials: str | None = _CREDS_HEADER,
                        authorization: str | None = _AUTH_HEADER,
                        vault: Vault = Depends(get_vault)) -> dict:
    """Revisa/cancela a solicitação de autorização (PATCH BACEN)."""
    creds = _creds_get(credentials, authorization, tenant_id, provider)
    return _provider(tenant_id, provider, {}, vault, creds).revisar_solicitacao_recorrencia(id_solic, campos)


# --- locations (QR de adesão — Jornada 2) --------------------------------------------


@router.post("/locations", response_model=dict, status_code=201)
def criar_location(tenant_id: str, provider: Provider = Provider.c6,
                   credentials: str | None = _CREDS_HEADER,
                   authorization: str | None = _AUTH_HEADER,
                   vault: Vault = Depends(get_vault)) -> dict:
    """Cria a location do QR de adesão da recorrência (Jornada 2)."""
    creds = _creds_get(credentials, authorization, tenant_id, provider)
    return _provider(tenant_id, provider, {}, vault, creds).criar_location_recorrencia()


@router.get("/locations/{loc_id}", response_model=dict)
def consultar_location(loc_id: str, tenant_id: str, provider: Provider = Provider.c6,
                       credentials: str | None = _CREDS_HEADER,
                       authorization: str | None = _AUTH_HEADER,
                       vault: Vault = Depends(get_vault)) -> dict:
    """Consulta a location (payload do QR)."""
    creds = _creds_get(credentials, authorization, tenant_id, provider)
    return _provider(tenant_id, provider, {}, vault, creds).consultar_location_recorrencia(loc_id)


@router.delete("/locations/{loc_id}/recorrencia", response_model=dict)
def desvincular_location(loc_id: str, tenant_id: str, provider: Provider = Provider.c6,
                         credentials: str | None = _CREDS_HEADER,
                         authorization: str | None = _AUTH_HEADER,
                         vault: Vault = Depends(get_vault)) -> dict:
    """Desvincula a recorrência da location (invalida o QR)."""
    creds = _creds_get(credentials, authorization, tenant_id, provider)
    return _provider(tenant_id, provider, {}, vault, creds).desvincular_location_recorrencia(loc_id)


# --- cobranças do ciclo (cobr — Jornada 3) --------------------------------------------


@router.put("/cobrancas/{txid}", response_model=dict, status_code=201)
def criar_cobranca(txid: str, body: CobrancaRecorrenteIn,
                   authorization: str | None = _AUTH_HEADER,
                   vault: Vault = Depends(get_vault)) -> dict:
    """Agenda a cobrança do ciclo (>= 2 dias antes do vencimento — regra BACEN)."""
    creds = resolve_request_credentials(authorization=authorization, explicit=body.credentials,
                                        tenant_id=body.tenant_id, provider=body.provider)
    p = _provider(body.tenant_id, body.provider, body.account_config, vault, creds)
    c = body.cobranca
    payload = {
        "idRec": c.id_rec,
        "calendario": {"dataDeVencimento": c.data_vencimento.isoformat()},
        "valor": {"original": f"{c.valor:.2f}"},
    }
    if c.info_adicional:
        payload["infoAdicional"] = c.info_adicional
    if c.extras:
        payload.update(c.extras)
    return p.criar_cobranca_recorrente(txid, payload)


@router.get("/cobrancas", response_model=dict)
def listar_cobrancas(tenant_id: str, inicio: str, fim: str, provider: Provider = Provider.c6,
                     credentials: str | None = _CREDS_HEADER,
                     authorization: str | None = _AUTH_HEADER,
                     vault: Vault = Depends(get_vault)) -> dict:
    """Lista cobranças do ciclo no período (RFC3339)."""
    creds = _creds_get(credentials, authorization, tenant_id, provider)
    return _provider(tenant_id, provider, {}, vault, creds).listar_cobrancas_recorrentes(inicio=inicio, fim=fim)


@router.get("/cobrancas/{txid}", response_model=dict)
def consultar_cobranca(txid: str, tenant_id: str, provider: Provider = Provider.c6,
                       credentials: str | None = _CREDS_HEADER,
                       authorization: str | None = _AUTH_HEADER,
                       vault: Vault = Depends(get_vault)) -> dict:
    """Consulta uma cobrança do ciclo (cobr) pelo txid."""
    creds = _creds_get(credentials, authorization, tenant_id, provider)
    return _provider(tenant_id, provider, {}, vault, creds).consultar_cobranca_recorrente(txid)


@router.patch("/cobrancas/{txid}", response_model=dict)
def revisar_cobranca(txid: str, campos: dict, tenant_id: str, provider: Provider = Provider.c6,
                     credentials: str | None = _CREDS_HEADER,
                     authorization: str | None = _AUTH_HEADER,
                     vault: Vault = Depends(get_vault)) -> dict:
    """Revisa a cobrança do ciclo (PATCH BACEN) — ex.: cancelamento antes da liquidação."""
    creds = _creds_get(credentials, authorization, tenant_id, provider)
    return _provider(tenant_id, provider, {}, vault, creds).revisar_cobranca_recorrente(txid, campos)


@router.post("/cobrancas/{txid}/retentativa/{data}", response_model=dict, status_code=201)
def retentar_cobranca(txid: str, data: str, tenant_id: str, provider: Provider = Provider.c6,
                      credentials: str | None = _CREDS_HEADER,
                      authorization: str | None = _AUTH_HEADER,
                      vault: Vault = Depends(get_vault)) -> dict:
    """Retentativa de liquidação para a data (YYYY-MM-DD) — pós vencimento não pago."""
    creds = _creds_get(credentials, authorization, tenant_id, provider)
    return _provider(tenant_id, provider, {}, vault, creds).retentar_cobranca_recorrente(txid, data)


# --- webhooks do Pix Automático ---------------------------------------------------------


@router.put("/config/webhooks", response_model=dict)
def configurar_webhooks(body: dict, tenant_id: str, provider: Provider = Provider.c6,
                        credentials: str | None = _CREDS_HEADER,
                        authorization: str | None = _AUTH_HEADER,
                        vault: Vault = Depends(get_vault)) -> dict:
    """Configura webhookrec e/ou webhookcobr: {"url_recorrencia": ..., "url_cobranca": ...}."""
    creds = _creds_get(credentials, authorization, tenant_id, provider)
    p = _provider(tenant_id, provider, {}, vault, creds)
    out: dict = {}
    if body.get("url_recorrencia"):
        out["webhookrec"] = p.configurar_webhook_recorrencia(body["url_recorrencia"])
    if body.get("url_cobranca"):
        out["webhookcobr"] = p.configurar_webhook_cobranca_recorrente(body["url_cobranca"])
    if not out:
        raise HTTPException(status_code=422, detail="informe url_recorrencia e/ou url_cobranca")
    return out
