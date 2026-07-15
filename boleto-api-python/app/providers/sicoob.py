# Provider Sicoob (756) — Cobrança Bancária v3 + Pix (BACEN) via API REST.
#
# Fontes: developers.sicoob.com.br (portal), doc Postman oficial da Cobrança v3
# e integrações de mercado. A doc oficial é notoriamente incompleta — pontos
# marcados com "TODO homologação" fecham na sandbox/homologação.
#
# Autenticação:
#   - OAuth2 client_credentials com SCOPES obrigatórios + mTLS (certificado
#     PFX emitido/cadastrado no portal; e-CNPJ ICP-Brasil em produção)
#   - token: https://auth.sicoob.com.br/auth/realms/cooperado/protocol/openid-connect/token
#   - header `client_id` em TODA request (peculiaridade Sicoob)
#   - sandbox: https://sandbox.sicoob.com.br/sicoob/sandbox (token estático do
#     portal, sem mTLS) — use SICOOB_BASE_URL/SICOOB_AUTH_URL para apontar
#
# APIs:
#   - Cobrança Bancária v3: /cobranca-bancaria/v3 (v2 descontinuada em 2025).
#     Boleto HÍBRIDO: quando a conta tem chave Pix vinculada, a emissão já
#     devolve pixCopiaECola (QR no boleto).
#   - Pix Recebimentos: /pix/api/v2 — PADRÃO BACEN, idêntico ao C6 → herdado
#     do BacenPixMixin (cob, cobv, lotecobv, revisões, listas).
#   - Conta Corrente v4 (extrato mensal): scopes cco_extrato/cco_saldo —
#     exposto em GET /extrato (validado no sandbox).
#
# Conciliação de BOLETO no Sicoob é por POLLING (consultas de liquidação),
# não webhook; Pix tem webhook BACEN. A lógica de agendamento do polling fica
# no PRODUTO consumidor — este gateway é interface de consumo (stateless).
from __future__ import annotations

import os
from typing import Any

from app.clients.oauth_mtls import OAuthMtlsClient
from app.providers.bacen_pix import BacenPixAutomaticoMixin, BacenPixMixin, BacenPixRecebidosMixin
from app.providers.base import BankProvider
from app.schemas import Cobranca, CobrancaOut, Pagador, Status, WebhookEvent

SICOOB_BASE = os.environ.get("SICOOB_BASE_URL", "https://api.sicoob.com.br")
SICOOB_AUTH = os.environ.get(
    "SICOOB_AUTH_URL",
    "https://auth.sicoob.com.br/auth/realms/cooperado/protocol/openid-connect/token",
)
# Scopes por área (o token só recebe o que for pedido)
SICOOB_SCOPES = [
    "cobranca_boletos_incluir", "cobranca_boletos_consultar", "cobranca_boletos_baixa",
    "cob.read", "cob.write", "cobv.read", "cobv.write",
    "lotecobv.read", "lotecobv.write", "pix.read", "pix.write",
    "webhook.read", "webhook.write", "payloadlocation.read", "payloadlocation.write",
    "cco_extrato", "cco_saldo",
]


class SicoobProvider(BacenPixMixin, BacenPixRecebidosMixin, BacenPixAutomaticoMixin, BankProvider):
    PIX_BASE = "/pix/api/v2"  # BACEN padrão, prefixo do Sicoob

    def _client(self) -> OAuthMtlsClient:
        return OAuthMtlsClient(
            base_url=SICOOB_BASE,
            auth_url=SICOOB_AUTH,
            client_id=self.credentials["client_id"],
            client_secret=self.credentials.get("client_secret", ""),
            pfx_base64=self.credentials.get("pfx_base64", ""),
            pfx_password=self.credentials.get("pfx_password", ""),
            scopes=self.credentials.get("scopes", SICOOB_SCOPES),
            default_headers={"client_id": self.credentials["client_id"]},  # Sicoob exige
            static_token=self.credentials.get("access_token", ""),  # sandbox: token do portal
        )

    # --- boleto registrado (Cobrança Bancária v3) ------------------------------

    def registrar(self, cobranca: Cobranca) -> CobrancaOut:
        payload = {
            "numeroCliente": self.account_config.get("numeroCliente"),
            "codigoModalidade": self.account_config.get("codigoModalidade", 1),
            "numeroContaCorrente": self.account_config.get("numeroContaCorrente"),
            "codigoEspecieDocumento": self.account_config.get("codigoEspecieDocumento", "DM"),
            "valor": float(cobranca.valor),
            "dataVencimento": cobranca.vencimento.isoformat(),
            "nossoNumero": cobranca.nosso_numero,
            "seuNumero": cobranca.seu_numero,
            "identificacaoEmissaoBoleto": self.account_config.get("identificacaoEmissaoBoleto", 1),
            "identificacaoDistribuicaoBoleto": self.account_config.get("identificacaoDistribuicaoBoleto", 1),
            "pagador": _pagador_sicoob(cobranca.pagador),
            "gerarPdf": bool(self.account_config.get("gerarPdf", False)),
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        data = self._client().request("POST", "/cobranca-bancaria/v3/boletos", json=payload)
        res = data.get("resultado") or data
        return CobrancaOut(
            id=str(res.get("nossoNumero") or res.get("seuNumero") or ""),
            status=_map_status(res.get("situacaoBoleto") or res.get("situacao")) or Status.registrado,
            linha_digitavel=res.get("linhaDigitavel"),
            codigo_barras=res.get("codigoBarras"),
            pix_copia_cola=res.get("pixCopiaECola") or res.get("qrCode"),  # boleto híbrido
            pdf_base64=res.get("pdfBoleto"),
            raw=data,
        )

    def consultar(self, cobranca_id: str) -> CobrancaOut:
        # Também é o que o PRODUTO consumidor chama no polling de liquidação.
        data = self._client().request(
            "GET", "/cobranca-bancaria/v3/boletos",
            params={
                "numeroCliente": self.account_config.get("numeroCliente"),
                "codigoModalidade": self.account_config.get("codigoModalidade", 1),
                "nossoNumero": cobranca_id,
            },
        )
        res = data.get("resultado") or data
        return CobrancaOut(
            id=cobranca_id,
            status=_map_status(res.get("situacaoBoleto") or res.get("situacao")) or Status.pendente,
            linha_digitavel=res.get("linhaDigitavel"),
            pix_copia_cola=res.get("pixCopiaECola"),
            raw=data,
        )

    def pdf(self, cobranca_id: str) -> CobrancaOut:
        # v3: segunda via dedicada (confirmada no sandbox: 200)
        data = self._client().request(
            "GET", "/cobranca-bancaria/v3/boletos/segunda-via",
            params={
                "numeroCliente": self.account_config.get("numeroCliente"),
                "codigoModalidade": self.account_config.get("codigoModalidade", 1),
                "nossoNumero": cobranca_id, "gerarPdf": "true",
            },
        )
        res = data.get("resultado") or data
        return CobrancaOut(id=cobranca_id, status=Status.pendente,
                           pdf_base64=res.get("pdfBoleto"), raw=data)

    def baixar(self, cobranca_id: str) -> CobrancaOut:
        # v3: baixa por comando.  TODO homologação: confirmar verbo/rota exatos.
        data = self._client().request(
            "POST", f"/cobranca-bancaria/v3/boletos/{cobranca_id}/baixar",
            json={
                "numeroCliente": self.account_config.get("numeroCliente"),
                "codigoModalidade": self.account_config.get("codigoModalidade", 1),
            },
        )
        return CobrancaOut(id=cobranca_id, status=Status.baixado, raw=data)

    def extrato(self, *, start_date: str, end_date: str) -> dict[str, Any]:
        """Extrato conta-corrente v4 (GET /extrato/{mes}/{ano}).

        A API do Sicoob é mensal: o período deve estar dentro do MESMO mês
        (diaInicial/diaFinal); períodos multi-mês retornam 422 no router.
        Validado no sandbox oficial (200).
        """
        from datetime import date as _date

        ini = _date.fromisoformat(start_date)
        fim = _date.fromisoformat(end_date)
        if (ini.year, ini.month) != (fim.year, fim.month):
            raise ValueError("extrato Sicoob é mensal: start_date e end_date devem estar no mesmo mês")
        return self._client().request(
            "GET", f"/conta-corrente/v4/extrato/{ini.month}/{ini.year}",
            params={"diaInicial": ini.day, "diaFinal": fim.day,
                    "numeroContaCorrente": self.account_config.get("numeroContaCorrente", 0)},
        )

    def normalizar_webhook(self, headers: dict[str, str], body: dict[str, Any]) -> WebhookEvent:
        # Sicoob: webhook é do PIX (BACEN — array `pix` de recebimentos).
        # Boleto continua por polling (consultar()).
        recebidos = body.get("pix") or []
        item = recebidos[0] if recebidos else body
        return WebhookEvent(
            event="pix.recebido",
            id=item.get("txid"),
            status=Status.liquidado,
            valor=item.get("valor"),
            paid_at=item.get("horario"),
            raw=body,
        )


def _pagador_sicoob(pagador: Pagador) -> dict[str, Any]:
    end = pagador.endereco or {}
    dados = {
        "numeroCpfCnpj": pagador.documento,
        "nome": pagador.nome,
        "endereco": end.get("endereco") or end.get("address") or end.get("street")
                    or end.get("logradouro"),
        "bairro": end.get("bairro") or end.get("neighborhood"),
        "cidade": end.get("cidade") or end.get("city"),
        "cep": end.get("cep") or end.get("zip_code"),
        "uf": end.get("uf") or end.get("state"),
        "email": end.get("email"),
    }
    return {k: v for k, v in dados.items() if v is not None}


def _map_status(s: str | None) -> Status | None:
    return {
        "EM ABERTO": Status.registrado, "EM_ABERTO": Status.registrado,
        "REGISTRADO": Status.registrado,
        "LIQUIDADO": Status.liquidado, "PAGO": Status.liquidado,
        "BAIXADO": Status.baixado, "BAIXADO POR SOLICITACAO": Status.baixado,
        "EXPIRADO": Status.expirado,
    }.get((s or "").upper())
