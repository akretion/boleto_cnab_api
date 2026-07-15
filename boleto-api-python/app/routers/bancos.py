# Catálogo de bancos/providers do gateway — descoberta programática.
#
# As capacidades são INTROSPECTADAS das classes de provider (método sobrescrito
# = capacidade real), então este endpoint nunca fica defasado do código.
from __future__ import annotations

from fastapi import APIRouter

from app.providers.base import BankProvider
from app.providers.brcobranca_proxy import BrcobrancaProxyProvider
from app.providers.c6 import C6Provider
from app.providers.sicoob import SicoobProvider

router = APIRouter(prefix="/bancos", tags=["bancos"])

# método do provider -> capacidade exposta
_CAPACIDADES = {
    "registrar": "boleto",
    "alterar": "boleto_alteracao",
    "pdf": "boleto_pdf",
    "baixar": "boleto_baixa",
    "criar_pix": "pix",
    "revisar_pix": "pix_revisao",
    "criar_lote_cobv": "pix_lote",
    "listar_pix_recebidos": "pix_recebidos",
    "configurar_webhook_pix": "webhook_pix_por_chave",
    "criar_recorrencia": "pix_automatico",
    "criar_bolepix": "bolepix",
    "extrato": "extrato",
    "listar_recebiveis": "conciliacao_cartao",
    "cadastrar_webhook": "webhook_banco",
}

# Mecanismo de autenticação DA API — único para todos os bancos:
# 1. POST /credenciais recebe os parâmetros DO BANCO (esquema próprio de cada um),
#    processa e armazena cifrado (zero-knowledge) → devolve token bapi_;
# 2. as demais chamadas autenticam com `Authorization: Bearer bapi_...` — a API
#    valida o token e usa as credenciais do banco por dentro.
_MECANISMO_API = {
    "cadastro": "POST /credenciais {tenant_id, provider, credentials:{<esquema do banco>}} -> token bapi_ (única vez)",
    "uso": "Authorization: Bearer bapi_... nas demais chamadas (a API valida e decifra em memória)",
    "revogacao": "DELETE /credenciais (com o Bearer)",
    "alternativas": [
        "credentials no corpo (POSTs) ou header X-Bank-Credentials (GET/DELETE) — stateless",
        "cofre VAULT__<tenant>__<provider>__* (env, fallback)",
    ],
}

# Esquema de credenciais PRÓPRIO de cada banco (conteúdo do campo `credentials`)
_ESQUEMA_C6 = {
    "client_id": "obrigatório (portal C6)",
    "client_secret": "obrigatório",
    "pfx_base64": "certificado mTLS do portal (PKCS12 em base64) — obrigatório",
    "pfx_password": "senha do certificado",
}
_ESQUEMA_SICOOB = {
    "client_id": "obrigatório (portal Sicoob; vai também no header de toda request)",
    "access_token": "sandbox: token estático do portal (dispensa OAuth/mTLS)",
    "client_secret": "produção: OAuth client_credentials com scopes",
    "pfx_base64": "produção: certificado mTLS/e-CNPJ (PKCS12 em base64)",
    "pfx_password": "senha do certificado",
    "scopes": "opcional (lista; default do provider)",
}

# 18 bancos suportados pelo caminho offline (engine brcobrança / CNAB)
_BANCOS_CNAB = [
    "ailos", "banco_brasil", "banco_brasilia", "banco_c6", "banco_nordeste",
    "banestes", "banrisul", "bradesco", "caixa", "citibank", "credisis", "hsbc",
    "itau", "safra", "santander", "sicoob", "sicredi", "unicred",
]


def _capacidades(klass: type) -> list[str]:
    caps = []
    for metodo, capacidade in _CAPACIDADES.items():
        impl = getattr(klass, metodo, None)
        base = getattr(BankProvider, metodo, None)
        if impl is not None and impl is not base:  # sobrescrito = suportado de fato
            caps.append(capacidade)
    return sorted(caps)


@router.get("", response_model=dict)
def listar() -> dict:
    """Bancos/providers disponíveis, capacidades reais e como autenticar."""
    return {
        "autenticacao_api": _MECANISMO_API,
        "bancos": [
            {
                "id": "c6",
                "nome": "C6 Bank",
                "codigo_banco": "336",
                "tipo": "rest",
                "capacidades": _capacidades(C6Provider),
                "credentials": _ESQUEMA_C6,
                "sandbox": "https://baas-api-sandbox.c6bank.info (seg-sex 7h-23h; mTLS + OAuth)",
                "documentacao": "docs/development/c6-rest.md",
            },
            {
                "id": "sicoob",
                "nome": "Sicoob",
                "codigo_banco": "756",
                "tipo": "rest",
                "capacidades": _capacidades(SicoobProvider),
                "credentials": _ESQUEMA_SICOOB,
                "sandbox": "https://sandbox.sicoob.com.br/sicoob/sandbox (token estático do portal)",
                "documentacao": "docs/development/sicoob-rest.md",
            },
            {
                "id": "brcobranca",
                "nome": "BrCobrança (engine Ruby — offline/CNAB)",
                "codigo_banco": None,
                "tipo": "offline",
                "capacidades": _capacidades(BrcobrancaProxyProvider) + ["carne", "remessa_cnab", "retorno_cnab"],
                "bancos_cnab": _BANCOS_CNAB,
                "observacao": "default quando `provider` vem vazio/omitido; não requer credenciais de banco",
                "documentacao": "docs/development/separacao-3-produtos.md",
            },
        ],
    }
