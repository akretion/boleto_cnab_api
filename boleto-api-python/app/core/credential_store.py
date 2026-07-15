# Tokenização de credenciais — cadastro devolve um token opaco; as credenciais
# ficam cifradas em repouso com chave DERIVADA DO PRÓPRIO TOKEN (zero-knowledge).
#
# Segurança:
#   - token = "bapi_" + 256 bits aleatórios (secrets), devolvido UMA única vez;
#   - chave AES-256-GCM derivada por HKDF-SHA256(token, salt) — o servidor NÃO
#     guarda o token (só o SHA-256 para lookup), logo NÃO consegue decifrar
#     sozinho: um vazamento do banco entrega blobs inúteis;
#   - AAD = "tenant:provider" amarra o blob ao contexto (anti troca de linha);
#   - revogação = DELETE da linha (token opaco, sem blocklist de JWT).
#
# Backend (auto-detectado):
#   - Postgres/Supabase se SUPABASE_DB_URL ou DATABASE_URL estiver no ambiente;
#   - SQLite local caso contrário (Render Free: disco efêmero — após deploy o
#     consumidor recebe 401 e recadastra, 1 chamada).
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
from abc import ABC, abstractmethod
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

TOKEN_PREFIX = "bapi_"
_HKDF_INFO = b"boleto-api credential token v1"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _derive_key(token: str, salt: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=_HKDF_INFO).derive(token.encode())


def _aad(tenant_id: str, provider: str) -> bytes:
    return f"{tenant_id}:{provider}".encode()


# --- backends -----------------------------------------------------------------


class CredentialStore(ABC):
    @abstractmethod
    def put(self, token_hash: str, tenant_id: str, provider: str,
            salt: bytes, nonce: bytes, ciphertext: bytes) -> None: ...

    @abstractmethod
    def get(self, token_hash: str) -> tuple[str, str, bytes, bytes, bytes] | None:
        """-> (tenant_id, provider, salt, nonce, ciphertext) ou None."""

    @abstractmethod
    def delete(self, token_hash: str) -> bool: ...


_SCHEMA = """
CREATE TABLE IF NOT EXISTS credential_tokens (
  token_hash TEXT PRIMARY KEY,
  tenant_id  TEXT NOT NULL,
  provider   TEXT NOT NULL,
  salt       {blob} NOT NULL,
  nonce      {blob} NOT NULL,
  ciphertext {blob} NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


class SqliteStore(CredentialStore):
    """SQLite local (default no Render Free — disco efêmero, ver cabeçalho)."""

    def __init__(self, path: str) -> None:
        self.path = path
        with self._conn() as c:
            c.execute(_SCHEMA.format(blob="BLOB"))

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def put(self, token_hash, tenant_id, provider, salt, nonce, ciphertext) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO credential_tokens (token_hash, tenant_id, provider, salt, nonce, ciphertext)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (token_hash, tenant_id, provider, salt, nonce, ciphertext),
            )

    def get(self, token_hash):
        with self._conn() as c:
            row = c.execute(
                "SELECT tenant_id, provider, salt, nonce, ciphertext FROM credential_tokens"
                " WHERE token_hash = ?", (token_hash,),
            ).fetchone()
        return (row[0], row[1], bytes(row[2]), bytes(row[3]), bytes(row[4])) if row else None

    def delete(self, token_hash) -> bool:
        with self._conn() as c:
            return c.execute(
                "DELETE FROM credential_tokens WHERE token_hash = ?", (token_hash,)
            ).rowcount > 0


class PostgresStore(CredentialStore):
    """Postgres/Supabase (SUPABASE_DB_URL ou DATABASE_URL). Import lazy do psycopg.

    Usa SCHEMA PRÓPRIO (default `boleto_api`, env CREDENTIAL_DB_SCHEMA) — nada no
    `public`: no Supabase o `public` é exposto pelo PostgREST/API auto-gerada, e o
    schema dedicado mantém a tabela fora dessa superfície e isolada de outros apps.
    """

    def __init__(self, dsn: str, schema: str | None = None) -> None:
        import psycopg  # lazy: só quem usa Postgres precisa da lib

        self._psycopg = psycopg
        self.dsn = dsn
        schema = schema or os.environ.get("CREDENTIAL_DB_SCHEMA", "boleto_api")
        if not schema.replace("_", "").isalnum():
            raise ValueError("CREDENTIAL_DB_SCHEMA inválido (use [a-z0-9_])")
        self._table = f'"{schema}".credential_tokens'
        with self._conn() as c:
            c.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            c.execute(_SCHEMA.format(blob="BYTEA").replace(
                "CREATE TABLE IF NOT EXISTS credential_tokens",
                f"CREATE TABLE IF NOT EXISTS {self._table}",
            ))

    def _conn(self):
        return self._psycopg.connect(self.dsn)

    def put(self, token_hash, tenant_id, provider, salt, nonce, ciphertext) -> None:
        with self._conn() as c:
            c.execute(
                f"INSERT INTO {self._table} (token_hash, tenant_id, provider, salt, nonce, ciphertext)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                (token_hash, tenant_id, provider, salt, nonce, ciphertext),
            )

    def get(self, token_hash):
        with self._conn() as c:
            row = c.execute(
                f"SELECT tenant_id, provider, salt, nonce, ciphertext FROM {self._table}"
                " WHERE token_hash = %s", (token_hash,),
            ).fetchone()
        return (row[0], row[1], bytes(row[2]), bytes(row[3]), bytes(row[4])) if row else None

    def delete(self, token_hash) -> bool:
        with self._conn() as c:
            cur = c.execute(f"DELETE FROM {self._table} WHERE token_hash = %s", (token_hash,))
            return cur.rowcount > 0


def get_store() -> CredentialStore:
    """Supabase/Postgres se houver DSN no ambiente; senão SQLite local."""
    dsn = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if dsn:
        return PostgresStore(dsn)
    return SqliteStore(os.environ.get("CREDENTIAL_DB_PATH", "credentials.db"))


# --- operações -----------------------------------------------------------------


def enroll(store: CredentialStore, tenant_id: str, provider: str,
           credentials: dict[str, Any]) -> str:
    """Cifra e armazena as credenciais; devolve o token (única vez que ele existe)."""
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    salt, nonce = os.urandom(16), os.urandom(12)
    ciphertext = AESGCM(_derive_key(token, salt)).encrypt(
        nonce, json.dumps(credentials).encode(), _aad(tenant_id, provider)
    )
    store.put(_hash(token), tenant_id, provider, salt, nonce, ciphertext)
    return token


def resolve(store: CredentialStore, token: str) -> tuple[str, str, dict[str, Any]] | None:
    """Token -> (tenant_id, provider, credentials) decifradas em memória; None se inválido."""
    if not token.startswith(TOKEN_PREFIX):
        return None
    row = store.get(_hash(token))
    if not row:
        return None
    tenant_id, provider, salt, nonce, ciphertext = row
    try:
        plaintext = AESGCM(_derive_key(token, salt)).decrypt(
            nonce, ciphertext, _aad(tenant_id, provider)
        )
    except InvalidTag:
        return None  # blob adulterado ou token errado com hash colidido — trata como inválido
    return tenant_id, provider, json.loads(plaintext)


def revoke(store: CredentialStore, token: str) -> bool:
    return token.startswith(TOKEN_PREFIX) and store.delete(_hash(token))


def credentials_from_bearer(
    store: CredentialStore, authorization: str | None, *, tenant_id: str, provider: str
) -> dict[str, Any] | None:
    """Resolve `Authorization: Bearer bapi_...` para as credenciais do banco.

    - Sem header ou Bearer que não seja `bapi_` -> None (segue o fluxo normal).
    - Token desconhecido/adulterado -> ValueError("token inválido")        (401)
    - Token de outro tenant/provider -> ValueError("token não corresponde") (403)
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization[7:].strip()
    if not token.startswith(TOKEN_PREFIX):
        return None
    resolved = resolve(store, token)
    if resolved is None:
        raise ValueError("token inválido")
    tok_tenant, tok_provider, creds = resolved
    if tok_tenant != tenant_id or tok_provider != provider:
        raise ValueError("token não corresponde ao tenant/provider do request")
    return creds
