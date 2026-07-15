# Roteador de providers + resolução de credenciais (request > cofre).
from __future__ import annotations

import base64
import binascii
import json
import os
from typing import Any

from app.core.vault import Vault
from app.providers.base import BankProvider
from app.providers.brcobranca_proxy import BrcobrancaProxyProvider
from app.providers.c6 import C6Provider
from app.providers.sicoob import SicoobProvider
from app.schemas import Provider

_PROVIDERS: dict[Provider, type[BankProvider]] = {
    Provider.brcobranca: BrcobrancaProxyProvider,
    Provider.c6: C6Provider,
    Provider.sicoob: SicoobProvider,
}

# Nome do banco no brcobrança para o fallback offline (método antigo).
_BRCOBRANCA_BANK: dict[Provider, str] = {
    Provider.c6: "banco_c6",
    Provider.sicoob: "sicoob",
}


def registered_ready(provider: Provider) -> bool:
    """Indica se a cobrança REGISTRADA (API do banco) está homologada e pronta.

    Enquanto C6/Sicoob não estão 100%, o padrão é `False` → cai no método antigo
    (brcobrança offline). Liga por banco com `C6_REGISTERED_READY=true` /
    `SICOOB_REGISTERED_READY=true` após a homologação.
    """
    if provider is Provider.brcobranca:
        return True
    return os.environ.get(f"{provider.value.upper()}_REGISTERED_READY", "").lower() in ("1", "true", "yes")


def build_provider(
    *,
    provider: Provider,
    tenant_id: str,
    account_config: dict[str, Any],
    vault: Vault,
    credentials: dict[str, Any] | None = None,
) -> BankProvider:
    # Fallback: C6/Sicoob ainda não 100% → trata pelo método antigo (brcobrança
    # offline), sem precisar de credencial de banco.
    if provider in _BRCOBRANCA_BANK and not registered_ready(provider):
        cfg = {**account_config, "bank": account_config.get("bank") or _BRCOBRANCA_BANK[provider]}
        return BrcobrancaProxyProvider(account_config=cfg, credentials={})

    klass = _PROVIDERS[provider]
    # offline (brcobrança) não precisa de credencial de banco.
    # Credenciais vindas NO REQUEST têm prioridade (nada gravado no servidor);
    # o cofre (VAULT__*) é o fallback para quem prefere provisionar no ambiente.
    creds: dict[str, Any] = {}
    if provider is not Provider.brcobranca:
        creds = credentials or vault.get_credentials(tenant_id, provider.value)
    return klass(account_config=account_config, credentials=creds)


def build_rest_provider(
    *,
    provider: Provider,
    tenant_id: str,
    account_config: dict[str, Any],
    vault: Vault,
    credentials: dict[str, Any] | None = None,
) -> BankProvider:
    """Provider REST direto, SEM fallback offline.

    Pix dinâmico e conciliação só existem na API do banco — não há equivalente
    CNAB para cair. `brcobranca` aqui é erro de contrato (o router traduz para 422).
    Credenciais do request têm prioridade sobre o cofre (só memória).
    """
    if provider is Provider.brcobranca:
        raise ValueError("operação exige provider REST (ex: c6); brcobranca é offline/CNAB")
    klass = _PROVIDERS[provider]
    creds = credentials or vault.get_credentials(tenant_id, provider.value)
    return klass(account_config=account_config, credentials=creds)


def credentials_from_header(value: str | None) -> dict[str, Any] | None:
    """Decodifica o header `X-Bank-Credentials` (JSON em base64) das rotas GET/DELETE.

    Mesmo contrato do campo `credentials` do corpo: {client_id, client_secret,
    pfx_base64, pfx_password}. Vive só na memória do request; nunca é logado
    nem persistido. Retorna None se o header não veio.
    """
    if not value:
        return None
    try:
        data = json.loads(base64.b64decode(value))
    except (binascii.Error, ValueError) as e:
        raise ValueError("X-Bank-Credentials inválido (esperado JSON em base64)") from e
    if not isinstance(data, dict):
        raise ValueError("X-Bank-Credentials deve conter um objeto JSON")
    return data
