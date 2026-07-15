# Cofre de credenciais por tenant (ponto crítico de segurança).
#
# O Boleto-API é STATEFUL: como a conciliação do Sicoob é por polling agendado,
# o serviço precisa das credenciais do tenant SEM um request na frente. Logo o
# cofre vive aqui — não no sistema consumidor.
#
# Esta é a INTERFACE. A implementação real deve usar KMS/Vault ou criptografia
# envelope no DB. NUNCA logar credencial/certificado. NUNCA versionar em git.
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any


class Vault(ABC):
    @abstractmethod
    def get_credentials(self, tenant_id: str, provider: str) -> dict[str, Any]:
        """Retorna { client_id, client_secret, pfx_base64, pfx_password, scopes?, ... }."""
        raise NotImplementedError


class CredentialNotFound(KeyError):
    """Tenant/provider sem credenciais no cofre. Subclasse de KeyError."""


class EnvVault(Vault):
    """Stub para desenvolvimento: lê de variáveis de ambiente.

    Formato: VAULT__<TENANT>__<PROVIDER>__<CHAVE>.
    NÃO usar em produção — trocar por KMS/Vault/DB cifrado.
    """

    def get_credentials(self, tenant_id: str, provider: str) -> dict[str, Any]:
        prefix = f"VAULT__{tenant_id}__{provider}__".upper()
        creds = {
            k[len(prefix):].lower(): v
            for k, v in os.environ.items()
            if k.upper().startswith(prefix)
        }
        if not creds:
            raise CredentialNotFound(f"tenant={tenant_id} provider={provider}")
        return creds


# Injeção simples; trocar por DI real no main.
def get_vault() -> Vault:
    # TODO: selecionar implementação por ENV (env|kms|vault|db).
    return EnvVault()
