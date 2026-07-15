# Cadastro de credenciais -> token opaco (tokenização; ver core/credential_store.py).
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from app.core import credential_store
from app.schemas import CredencialIn, CredencialOut

router = APIRouter(prefix="/credenciais", tags=["credenciais"])


@router.post("", response_model=CredencialOut, status_code=201)
def cadastrar(body: CredencialIn) -> CredencialOut:
    """Armazena as credenciais cifradas (chave derivada do token) e devolve o token.

    O token é exibido UMA única vez — o servidor não consegue recuperá-lo nem
    decifrar as credenciais sem ele. Use-o nas demais rotas via
    `Authorization: Bearer bapi_...`.
    """
    store = credential_store.get_store()
    token = credential_store.enroll(store, body.tenant_id, body.provider.value, body.credentials)
    return CredencialOut(token=token, tenant_id=body.tenant_id, provider=body.provider)


@router.delete("", status_code=204)
def revogar(authorization: str = Header(description="Bearer bapi_...")) -> None:
    """Revoga o token imediatamente (apaga o registro cifrado)."""
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="use Authorization: Bearer bapi_...")
    store = credential_store.get_store()
    if not credential_store.revoke(store, authorization[7:].strip()):
        raise HTTPException(status_code=401, detail="token inválido")
