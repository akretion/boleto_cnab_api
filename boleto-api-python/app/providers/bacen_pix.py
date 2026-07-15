# Pix BACEN — mixin compartilhado entre providers.
#
# A API Pix é PADRONIZADA pelo BACEN: /cob, /cobv, /lotecobv, /webhook são
# idênticos em todos os PSPs. O que muda por banco é autenticação e o prefixo
# base (C6: /v2/pix; Sicoob: /pix/api/v2). Este mixin implementa o dialeto uma
# única vez; cada provider define PIX_BASE e fornece _client().
from __future__ import annotations

from typing import Any

from app.schemas import Pagador, PixCobranca, PixCobrancaOut, Status


class BacenPixMixin:
    PIX_BASE = "/v2/pix"  # override por provider

    def criar_pix(self, pix: PixCobranca) -> PixCobrancaOut:
        chave = pix.chave or self.account_config.get("chave_pix")
        if not chave:
            raise ValueError("chave Pix ausente (pix.chave ou account_config.chave_pix)")

        payload: dict[str, Any] = {
            "valor": {"original": f"{pix.valor:.2f}"},
            "chave": chave,
        }
        if pix.descricao:
            payload["solicitacaoPagador"] = pix.descricao

        if pix.data_vencimento:  # cobv — exige devedor com endereço e txid do emissor
            if not pix.devedor:
                raise ValueError("cobv exige devedor")
            if not pix.txid:
                raise ValueError("cobv exige txid ([a-zA-Z0-9]{26,35})")
            payload["calendario"] = {
                "dataDeVencimento": pix.data_vencimento.isoformat(),
                "validadeAposVencimento": pix.validade_apos_vencimento,
            }
            payload["devedor"] = _devedor(pix.devedor)
            data = self._client().request("PUT", f"{self.PIX_BASE}/cobv/{pix.txid}", json=payload)
        else:  # cob imediata — com txid (PUT) ou o banco gera (POST)
            payload["calendario"] = {"expiracao": pix.expiracao_segundos}
            if pix.devedor:
                payload["devedor"] = _devedor_simples(pix.devedor)
            if pix.txid:
                data = self._client().request("PUT", f"{self.PIX_BASE}/cob/{pix.txid}", json=payload)
            else:
                data = self._client().request("POST", f"{self.PIX_BASE}/cob", json=payload)

        return _pix_out(data)

    def consultar_pix(self, txid: str, *, vencimento: bool = False) -> PixCobrancaOut:
        tipo = "cobv" if vencimento else "cob"
        data = self._client().request("GET", f"{self.PIX_BASE}/{tipo}/{txid}")
        return _pix_out(data)

    def revisar_pix(self, txid: str, campos: dict[str, Any], *, vencimento: bool = False) -> PixCobrancaOut:
        """PATCH de revisão da cobrança (valor, solicitacaoPagador, calendario...)."""
        tipo = "cobv" if vencimento else "cob"
        data = self._client().request("PATCH", f"{self.PIX_BASE}/{tipo}/{txid}", json=campos)
        return _pix_out(data)

    def listar_pix(self, *, inicio: str, fim: str, vencimento: bool = False) -> dict[str, Any]:
        """Lista cobranças do período (RFC3339: 2026-07-15T00:00:00Z)."""
        tipo = "cobv" if vencimento else "cob"
        return self._client().request("GET", f"{self.PIX_BASE}/{tipo}",
                                      params={"inicio": inicio, "fim": fim})

    # --- lote de cobv ------------------------------------------------------------

    def criar_lote_cobv(self, lote_id: str, descricao: str, cobsv: list[dict[str, Any]]) -> dict[str, Any]:
        return self._client().request(
            "PUT", f"{self.PIX_BASE}/lotecobv/{lote_id}", json={"descricao": descricao, "cobsv": cobsv}
        )

    def revisar_lote_cobv(self, lote_id: str, cobsv: list[dict[str, Any]]) -> dict[str, Any]:
        return self._client().request("PATCH", f"{self.PIX_BASE}/lotecobv/{lote_id}", json={"cobsv": cobsv})

    def consultar_lote_cobv(self, lote_id: str) -> dict[str, Any]:
        return self._client().request("GET", f"{self.PIX_BASE}/lotecobv/{lote_id}")

    def listar_lotes_cobv(self, *, inicio: str, fim: str) -> dict[str, Any]:
        return self._client().request("GET", f"{self.PIX_BASE}/lotecobv",
                                      params={"inicio": inicio, "fim": fim})


# --- mapeamentos BACEN ------------------------------------------------------------


def _devedor(pagador: Pagador) -> dict[str, Any]:
    # cobv: BACEN exige endereço do devedor
    end = pagador.endereco or {}
    dev = _devedor_simples(pagador)
    dev.update(
        logradouro=end.get("logradouro") or end.get("street"),
        cidade=end.get("cidade") or end.get("city"),
        uf=end.get("uf") or end.get("state"),
        cep=end.get("cep") or end.get("zip_code"),
    )
    return {k: v for k, v in dev.items() if v is not None}


def _devedor_simples(pagador: Pagador) -> dict[str, Any]:
    doc_key = "cpf" if len(pagador.documento) == 11 else "cnpj"
    return {"nome": pagador.nome, doc_key: pagador.documento}


def _pix_out(data: dict[str, Any]) -> PixCobrancaOut:
    loc = data.get("loc") or {}
    return PixCobrancaOut(
        txid=data.get("txid"),
        status=_map_pix_status(data.get("status")) or Status.registrado,
        pix_copia_cola=data.get("pixCopiaECola") or data.get("brcode"),  # Sicoob usa brcode
        location=loc.get("location") or data.get("location"),
        raw=data,
    )


def _map_pix_status(s: str | None) -> Status | None:
    """Pix BACEN: ATIVA / CONCLUIDA / REMOVIDA_*."""
    s = (s or "").upper()
    if s.startswith("REMOVIDA"):
        return Status.baixado
    return {"ATIVA": Status.registrado, "CONCLUIDA": Status.liquidado}.get(s)


class BacenPixRecebidosMixin:
    """P_05/P_06 BACEN: Pix recebidos (money-in), devoluções e webhook por chave."""

    def listar_pix_recebidos(self, *, inicio: str, fim: str) -> dict[str, Any]:
        return self._client().request("GET", f"{self.PIX_BASE}/pix",
                                      params={"inicio": inicio, "fim": fim})

    def consultar_pix_recebido(self, e2eid: str) -> dict[str, Any]:
        return self._client().request("GET", f"{self.PIX_BASE}/pix/{e2eid}")

    def devolver_pix(self, e2eid: str, devolucao_id: str, valor: str) -> dict[str, Any]:
        return self._client().request(
            "PUT", f"{self.PIX_BASE}/pix/{e2eid}/devolucao/{devolucao_id}",
            json={"valor": valor},
        )

    def consultar_devolucao(self, e2eid: str, devolucao_id: str) -> dict[str, Any]:
        return self._client().request("GET", f"{self.PIX_BASE}/pix/{e2eid}/devolucao/{devolucao_id}")

    # webhook BACEN por CHAVE (banco chama a URL quando um Pix cai naquela chave)
    def configurar_webhook_pix(self, chave: str, url: str) -> dict[str, Any]:
        return self._client().request("PUT", f"{self.PIX_BASE}/webhook/{chave}",
                                      json={"webhookUrl": url})

    def consultar_webhook_pix(self, chave: str) -> dict[str, Any]:
        return self._client().request("GET", f"{self.PIX_BASE}/webhook/{chave}")

    def remover_webhook_pix(self, chave: str) -> dict[str, Any]:
        return self._client().request("DELETE", f"{self.PIX_BASE}/webhook/{chave}")

    def listar_webhooks_pix(self) -> dict[str, Any]:
        return self._client().request("GET", f"{self.PIX_BASE}/webhook")


class BacenPixAutomaticoMixin:
    """Pix Automático BACEN (rec/solicrec/locrec/cobr/webhookrec|cobr).

    Débito recorrente via Pix: o pagador autoriza UMA vez (app do banco ou QR) e
    as cobranças do ciclo debitam automaticamente. O AGENDAMENTO de cada `cobr`
    (>= 2 dias antes do vencimento) é responsabilidade do PRODUTO consumidor —
    este gateway é interface de consumo (stateless), por decisão de arquitetura.
    """

    # --- recorrência (rec) ------------------------------------------------------

    def criar_recorrencia(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._client().request("POST", f"{self.PIX_BASE}/rec", json=payload)

    def consultar_recorrencia(self, id_rec: str, *, txid: str | None = None) -> dict[str, Any]:
        params = {"txid": txid} if txid else None
        return self._client().request("GET", f"{self.PIX_BASE}/rec/{id_rec}", params=params)

    def revisar_recorrencia(self, id_rec: str, campos: dict[str, Any]) -> dict[str, Any]:
        """Revisão/gestão (Jornada 4) — inclui cancelamento (status CANCELADA)."""
        return self._client().request("PATCH", f"{self.PIX_BASE}/rec/{id_rec}", json=campos)

    def listar_recorrencias(self, *, inicio: str, fim: str) -> dict[str, Any]:
        return self._client().request("GET", f"{self.PIX_BASE}/rec",
                                      params={"inicio": inicio, "fim": fim})

    # --- solicitação de confirmação (solicrec — Jornada 1) ------------------------

    def criar_solicitacao_recorrencia(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._client().request("POST", f"{self.PIX_BASE}/solicrec", json=payload)

    def consultar_solicitacao_recorrencia(self, id_solic: str) -> dict[str, Any]:
        return self._client().request("GET", f"{self.PIX_BASE}/solicrec/{id_solic}")

    def revisar_solicitacao_recorrencia(self, id_solic: str, campos: dict[str, Any]) -> dict[str, Any]:
        return self._client().request("PATCH", f"{self.PIX_BASE}/solicrec/{id_solic}", json=campos)

    # --- location do payload (locrec — QR de adesão, Jornada 2) --------------------

    def criar_location_recorrencia(self) -> dict[str, Any]:
        return self._client().request("POST", f"{self.PIX_BASE}/locrec")

    def consultar_location_recorrencia(self, loc_id: str) -> dict[str, Any]:
        return self._client().request("GET", f"{self.PIX_BASE}/locrec/{loc_id}")

    def desvincular_location_recorrencia(self, loc_id: str) -> dict[str, Any]:
        return self._client().request("DELETE", f"{self.PIX_BASE}/locrec/{loc_id}/idRec")

    # --- cobrança recorrente (cobr — Jornada 3) -------------------------------------

    def criar_cobranca_recorrente(self, txid: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._client().request("PUT", f"{self.PIX_BASE}/cobr/{txid}", json=payload)

    def consultar_cobranca_recorrente(self, txid: str) -> dict[str, Any]:
        return self._client().request("GET", f"{self.PIX_BASE}/cobr/{txid}")

    def revisar_cobranca_recorrente(self, txid: str, campos: dict[str, Any]) -> dict[str, Any]:
        return self._client().request("PATCH", f"{self.PIX_BASE}/cobr/{txid}", json=campos)

    def listar_cobrancas_recorrentes(self, *, inicio: str, fim: str) -> dict[str, Any]:
        return self._client().request("GET", f"{self.PIX_BASE}/cobr",
                                      params={"inicio": inicio, "fim": fim})

    def retentar_cobranca_recorrente(self, txid: str, data: str) -> dict[str, Any]:
        """Solicita retentativa de liquidação para a data (YYYY-MM-DD)."""
        return self._client().request("POST", f"{self.PIX_BASE}/cobr/{txid}/retentativa/{data}")

    # --- webhooks do Pix Automático ----------------------------------------------------

    def configurar_webhook_recorrencia(self, url: str) -> dict[str, Any]:
        return self._client().request("PUT", f"{self.PIX_BASE}/webhookrec",
                                      json={"webhookUrl": url})

    def configurar_webhook_cobranca_recorrente(self, url: str) -> dict[str, Any]:
        return self._client().request("PUT", f"{self.PIX_BASE}/webhookcobr",
                                      json={"webhookUrl": url})
