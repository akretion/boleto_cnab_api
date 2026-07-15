# Resolução de credenciais do request (compartilhada pelos routers).
#
# Ordem de precedência:
#   1. Authorization: Bearer bapi_...   (token do /credenciais — decifra em memória)
#   2. credentials no corpo (POST) ou header X-Bank-Credentials (GET/DELETE)
#   3. cofre do servidor (VAULT__*) — resolvido depois, no registry
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.core import credential_store
from app.schemas import Provider


def resolve_request_credentials(
    *,
    authorization: str | None,
    explicit: dict[str, Any] | None,
    tenant_id: str,
    provider: Provider,
) -> dict[str, Any] | None:
    """Bearer bapi_ -> credenciais do token; senão as explícitas do request; senão None."""
    if authorization and credential_store.TOKEN_PREFIX in authorization:
        try:
            bearer = credential_store.credentials_from_bearer(
                credential_store.get_store(), authorization,
                tenant_id=tenant_id, provider=provider.value,
            )
        except ValueError as e:
            status = 403 if "não corresponde" in str(e) else 401
            raise HTTPException(status_code=status, detail=str(e)) from e
        if bearer is not None:
            return bearer
    return explicit
