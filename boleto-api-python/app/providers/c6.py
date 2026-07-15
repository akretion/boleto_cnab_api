# Provider C6 (336) — boleto registrado, Pix dinâmico, Bolepix, extrato,
# conciliação e webhooks via API REST.
#
# Contrato extraído das specs oficiais em docs/development/Banco C6/ e VALIDADO
# no sandbox real (roteiro de homologação v3.0):
#   autenticação.yaml   — mTLS (PFX) + OAuth client_credentials em /v1/auth
#   boleto-bancário.yaml — /v1/bank_slips (emitir, consultar, pdf, alterar, cancelar)
#   pix.yaml            — /v2/pix (cob, cobv, lotecobv; padrão BACEN)
#   bolepix.yaml        — /v2/bank_slips (boleto híbrido com Pix EVP)
#   extrato.yaml        — /v1/statement
#   notificações.yaml   — /v1/webhooks (cadastro de webhook no banco)
#   transações-e-recebíveis-c6-pay.yaml — /v1/c6pay/statement (receivables, transactions)
#
# Carteiras (billing_scheme): sandbox = "21", produção = "15".
# Sandbox: seg-sex 7h-23h (fora disso a API do banco não responde).
#
# Assincronia (aprendida no sandbox): após emitir/alterar, o registro passa pela
# CIP; cancelamentos nesse intervalo respondem 400/422 "já existe uma requisição
# em processamento/sujeita a aprovação". O provider re-tenta por uma janela curta
# e, se ainda pendente, levanta ProcessamentoPendente (router -> 409).
from __future__ import annotations

import os
import time
from typing import Any

import httpx

from app.clients.oauth_mtls import OAuthMtlsClient
from app.providers.bacen_pix import BacenPixAutomaticoMixin, BacenPixMixin, BacenPixRecebidosMixin, _devedor, _devedor_simples, _map_pix_status, _pix_out
from app.providers.base import BankProvider
from app.schemas import (
    Cobranca,
    CobrancaOut,
    ConciliacaoOut,
    Pagador,
    PixCobranca,
    PixCobrancaOut,
    Status,
    WebhookEvent,
)

C6_BASE = os.environ.get("C6_BASE_URL", "https://baas-api-sandbox.c6bank.info")
C6_AUTH = os.environ.get("C6_AUTH_URL", f"{C6_BASE}/v1/auth")
# Carteira de cobrança: "21" (sandbox) / "15" (produção)
C6_BILLING_SCHEME = os.environ.get("C6_BILLING_SCHEME", "21")
# Identificação do parceiro (headers opcionais em toda a API do C6)
C6_PARTNER_HEADERS = {
    k: v
    for k, v in {
        "partner-software-name": os.environ.get("C6_PARTNER_NAME", "boleto-api"),
        "partner-software-version": os.environ.get("C6_PARTNER_VERSION", ""),
    }.items()
    if v
}
# Janela de re-tentativa para operações bloqueadas pela CIP (400/422 transitório)
C6_CIP_RETRIES = int(os.environ.get("C6_CIP_RETRIES", "3"))
C6_CIP_WAIT = float(os.environ.get("C6_CIP_WAIT_SECONDS", "5"))


class ProcessamentoPendente(Exception):
    """Registro ainda em processamento na CIP — re-tente em instantes (HTTP 409)."""


def _cip_pendente(e: httpx.HTTPStatusError) -> bool:
    return e.response.status_code in (400, 422) and (
        "existe uma requisi" in e.response.text or "processamento" in e.response.text
    )


class C6Provider(BacenPixMixin, BacenPixRecebidosMixin, BacenPixAutomaticoMixin, BankProvider):
    PIX_BASE = "/v2/pix"

    def _client(self) -> OAuthMtlsClient:
        return OAuthMtlsClient(
            base_url=C6_BASE,
            auth_url=C6_AUTH,
            client_id=self.credentials["client_id"],
            client_secret=self.credentials.get("client_secret", ""),
            pfx_base64=self.credentials.get("pfx_base64", ""),
            pfx_password=self.credentials.get("pfx_password", ""),
            default_headers=C6_PARTNER_HEADERS,
            static_token=self.credentials.get("access_token", ""),  # contrato unificado c/ Sicoob
        )

    # --- boleto registrado (/v1/bank_slips) -----------------------------------

    def registrar(self, cobranca: Cobranca) -> CobrancaOut:
        payload: dict[str, Any] = {
            # external_reference_id: ^[a-zA-Z0-9]{1,10}$, único por cliente
            "external_reference_id": cobranca.seu_numero or cobranca.nosso_numero,
            "amount": float(cobranca.valor),
            "due_date": cobranca.vencimento.isoformat(),
            "billing_scheme": self.account_config.get("billing_scheme", C6_BILLING_SCHEME),
            "payer": _payer(cobranca.pagador),
        }
        if cobranca.nosso_numero:
            payload["our_number"] = cobranca.nosso_numero  # ^\d{1,10}$
        for campo, chave in (("desconto", "discount"), ("juros", "interest"), ("multa", "fine")):
            valor = getattr(cobranca, campo)
            if valor:
                payload[chave] = valor
        if self.account_config.get("instructions"):
            payload["instructions"] = self.account_config["instructions"]

        data = self._client().request("POST", "/v1/bank_slips/", json=payload)
        return _boleto_out(data, default_status=Status.registrado)

    def consultar(self, cobranca_id: str) -> CobrancaOut:
        data = self._client().request("GET", f"/v1/bank_slips/{cobranca_id}")
        return _boleto_out(data, default_status=Status.pendente)

    def pdf(self, cobranca_id: str) -> CobrancaOut:
        # A consulta devolve base64_pdf_file no próprio corpo; o endpoint /pdf
        # dedicado fica de fallback.
        out = self.consultar(cobranca_id)
        if not out.pdf_base64:
            data = self._client().request("GET", f"/v1/bank_slips/{cobranca_id}/pdf")
            if isinstance(data, dict):
                out.pdf_base64 = data.get("base64_pdf_file")
        return out

    def alterar(self, cobranca_id: str, campos: dict[str, Any]) -> CobrancaOut:
        """Altera boleto já emitido (amount, due_date, discount, interest, fine)."""
        data = self._cip_retry("PUT", f"/v1/bank_slips/{cobranca_id}", json=campos)
        return _boleto_out(data, default_status=Status.registrado)

    def baixar(self, cobranca_id: str) -> CobrancaOut:
        # Cancelamento é PUT e responde 204 (sem corpo)
        data = self._cip_retry("PUT", f"/v1/bank_slips/{cobranca_id}/cancel")
        return CobrancaOut(id=cobranca_id, status=Status.baixado, raw=data or None)

    def _cip_retry(self, method: str, path: str, json: Any = None) -> dict[str, Any]:
        # Registro assíncrono na CIP: re-tenta 400/422 transitório por janela curta.
        for _ in range(C6_CIP_RETRIES):
            try:
                return self._client().request(method, path, json=json)
            except httpx.HTTPStatusError as e:
                if not _cip_pendente(e):
                    raise
                time.sleep(C6_CIP_WAIT)
        raise ProcessamentoPendente(
            "registro em processamento no banco (CIP); re-tente em instantes"
        )

    # --- Bolepix (/v2/bank_slips — boleto híbrido com Pix EVP) -------------------
    # Schema próprio do v2: external_reference_id ^[A-Z0-9]{26}$; address do payer
    # unificado (rua+número num campo) + neighborhood.

    def criar_bolepix(self, dados: dict[str, Any]) -> CobrancaOut:
        data = self._client().request("POST", "/v2/bank_slips/", json=dados)
        return _bolepix_out(data, default_status=Status.registrado)

    def consultar_bolepix(self, external_reference_id: str) -> CobrancaOut:
        data = self._client().request("GET", f"/v2/bank_slips/{external_reference_id}")
        return _bolepix_out(data, default_status=Status.pendente)

    def pdf_bolepix(self, external_reference_id: str) -> CobrancaOut:
        out = self.consultar_bolepix(external_reference_id)
        if not out.pdf_base64:
            data = self._client().request("GET", f"/v2/bank_slips/{external_reference_id}/pdf")
            if isinstance(data, dict):
                out.pdf_base64 = data.get("base64_pdf_file")
        return out

    def cancelar_bolepix(self, external_reference_id: str) -> CobrancaOut:
        data = self._cip_retry("PUT", f"/v2/bank_slips/{external_reference_id}/cancel")
        return CobrancaOut(id=external_reference_id, status=Status.baixado, raw=data or None)

    # --- extrato (/v1/statement) --------------------------------------------------

    def extrato(self, *, start_date: str, end_date: str) -> dict[str, Any]:
        return self._client().request(
            "GET", "/v1/statement/", params={"start_date": start_date, "end_date": end_date}
        )

    # --- webhooks no banco (/v1/webhooks) ------------------------------------------

    def cadastrar_webhook(self, *, url: str, service: str) -> dict[str, Any]:
        """Registra a URL de notificação no banco (service: BANK_SLIP | CHECKOUT)."""
        return self._client().request("POST", "/v1/webhooks/", json={"url": url, "service": service})

    def consultar_webhook(self, *, service: str) -> dict[str, Any]:
        return self._client().request("GET", "/v1/webhooks/", params={"service": service})

    def remover_webhook(self, *, service: str) -> dict[str, Any]:
        return self._client().request("DELETE", "/v1/webhooks/", params={"service": service})

    # --- conciliação (C6 Pay /v1/c6pay/statement) -------------------------------

    def listar_recebiveis(self, *, start_date: str, end_date: str, page: int, size: int) -> ConciliacaoOut:
        data = self._client().request(
            "GET", "/v1/c6pay/statement/receivables",
            params={"start_date": start_date, "end_date": end_date, "page": page, "size": size},
        )
        return _conciliacao_out(data, "receivables")

    def listar_transacoes(self, *, start_date: str, end_date: str, page: int, size: int) -> ConciliacaoOut:
        data = self._client().request(
            "GET", "/v1/c6pay/statement/transactions",
            params={"start_date": start_date, "end_date": end_date, "page": page, "size": size},
        )
        return _conciliacao_out(data, "transactions")

    # --- webhook -----------------------------------------------------------------

    def normalizar_webhook(self, headers: dict[str, str], body: dict[str, Any]) -> WebhookEvent:
        # A notificação do C6 traz o próprio objeto (boleto ou pix) com o novo status.
        # TODO homologação: o C6 não documenta assinatura no payload — autenticidade
        # garantida pelo token de rota (ver routers/webhooks.py) até definição.
        pagamentos = body.get("payments") or []
        pago = pagamentos[0] if pagamentos else {}
        txid = body.get("txid")
        if body.get("idRec"):  # Pix Automático (webhookrec/webhookcobr)
            return WebhookEvent(
                event="pix_automatico.cobranca" if txid else "pix_automatico.recorrencia",
                id=txid or body.get("idRec"),
                status=_map_pix_status(body.get("status")),
                raw=body,
            )
        status = _map_status(body.get("status")) or _map_pix_status(body.get("status"))
        return WebhookEvent(
            event="pix.atualizada" if txid else "cobranca.atualizada",
            id=txid or body.get("id") or body.get("external_reference_id"),
            status=status,
            paid_at=pago.get("date"),
            valor=pago.get("amount"),
            raw=body,
        )


# --- mapeamentos ------------------------------------------------------------------


def _payer(pagador: Pagador) -> dict[str, Any]:
    payer: dict[str, Any] = {
        "name": pagador.nome,
        "tax_id": pagador.documento,  # sem máscara, zeros à esquerda preservados
    }
    end = pagador.endereco or {}
    if end.get("email"):
        payer["email"] = end["email"]
    address = {
        "street": end.get("street") or end.get("logradouro"),
        "number": end.get("number") or end.get("numero"),
        "complement": end.get("complement") or end.get("complemento"),
        "city": end.get("city") or end.get("cidade"),
        "state": end.get("state") or end.get("uf"),
        "zip_code": end.get("zip_code") or end.get("cep"),
    }
    address = {k: v for k, v in address.items() if v is not None}
    if address:
        payer["address"] = address
    return payer


def _boleto_out(data: dict[str, Any], *, default_status: Status) -> CobrancaOut:
    return CobrancaOut(
        id=data.get("id"),
        status=_map_status(data.get("status")) or default_status,
        linha_digitavel=data.get("digitable_line"),
        codigo_barras=data.get("bar_code"),
        pdf_base64=data.get("base64_pdf_file"),
        raw=data,
    )


def _bolepix_out(data: dict[str, Any], *, default_status: Status) -> CobrancaOut:
    slip = (data.get("payment_method") or {}).get("bank_slip") or {}
    pix = (data.get("payment_method") or {}).get("pix") or {}
    return CobrancaOut(
        id=data.get("external_reference_id") or slip.get("number") or data.get("id"),
        status=_map_status(data.get("status")) or default_status,
        linha_digitavel=slip.get("digitable_line") or data.get("digitable_line"),
        codigo_barras=slip.get("bar_code") or data.get("bar_code"),
        pix_copia_cola=pix.get("qr_code") or pix.get("emv") or pix.get("copy_and_paste"),
        pdf_base64=data.get("base64_pdf_file"),
        raw=data,
    )


def _conciliacao_out(data: dict[str, Any], key: str) -> ConciliacaoOut:
    return ConciliacaoOut(
        page=data.get("page"),
        last_page=data.get("last_page") or data.get("last-page"),
        total_items=data.get("items") if isinstance(data.get("items"), int) else None,
        items=data.get(key) or [],
    )


def _map_status(s: str | None) -> Status | None:
    """Boleto C6: CREATED / PAID / CANCELLED (+ sinônimos defensivos)."""
    return {
        "CREATED": Status.registrado, "REGISTERED": Status.registrado, "ACTIVE": Status.registrado,
        "PAID": Status.liquidado, "SETTLED": Status.liquidado,
        "CANCELLED": Status.baixado, "WRITTEN_OFF": Status.baixado,
        "EXPIRED": Status.expirado,
    }.get((s or "").upper())

