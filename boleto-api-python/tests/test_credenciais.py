# Tokenização de credenciais: POST /credenciais -> token; Bearer nas demais rotas.
import sqlite3

import pytest

from app.core import credential_store


@pytest.fixture(autouse=True)
def sqlite_tmp(tmp_path, monkeypatch):
    # backend SQLite isolado por teste; sem SUPABASE_DB_URL/DATABASE_URL
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("CREDENTIAL_DB_PATH", str(tmp_path / "creds.db"))


def _cadastrar(client, tenant="empresa1", provider="c6"):
    r = client.post("/credenciais", json={
        "tenant_id": tenant, "provider": provider,
        "credentials": {"client_id": "cid-token", "client_secret": "s3c"},
    })
    assert r.status_code == 201, r.text
    return r.json()["token"]


def test_cadastro_devolve_token_opaco(client):
    token = _cadastrar(client)
    assert token.startswith("bapi_")
    assert len(token) > 40


def test_credenciais_cifradas_em_repouso_sem_token_nao_decifra(client, tmp_path):
    _cadastrar(client)
    # inspeciona o banco direto: nada de client_secret em claro, token não armazenado
    db = sqlite3.connect(str(tmp_path / "creds.db"))
    rows = db.execute("SELECT token_hash, ciphertext FROM credential_tokens").fetchall()
    assert len(rows) == 1
    token_hash, ciphertext = rows[0]
    blob = bytes(ciphertext)
    assert b"cid-token" not in blob and b"s3c" not in blob  # cifrado de verdade
    assert not token_hash.startswith("bapi_")  # só o hash, nunca o token


def test_bearer_usa_credenciais_do_token(client, monkeypatch):
    token = _cadastrar(client)
    used = {}

    def fake_request(self, method, path, json=None, params=None):
        used["client_id"] = self.client_id
        return {"txid": "T1", "status": "ATIVA"}

    monkeypatch.setattr("app.clients.oauth_mtls.OAuthMtlsClient.request", fake_request)

    body = {"tenant_id": "empresa1", "provider": "c6",
            "account_config": {"chave_pix": "k"}, "pix": {"valor": "1.00"}}
    r = client.post("/pix", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert used["client_id"] == "cid-token"  # veio do token, sem VAULT e sem corpo


def test_bearer_em_get_e_conciliacao(client, monkeypatch):
    token = _cadastrar(client)
    monkeypatch.setattr(
        "app.clients.oauth_mtls.OAuthMtlsClient.request",
        lambda self, method, path, json=None, params=None: {"txid": "T", "status": "CONCLUIDA", "page": 1, "receivables": []},
    )
    r = client.get("/pix/T", params={"tenant_id": "empresa1", "provider": "c6"},
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    r = client.get("/conciliacao/recebiveis",
                   params={"tenant_id": "empresa1", "provider": "c6",
                           "start_date": "2026-07-01", "end_date": "2026-07-10"},
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text


def test_token_invalido_401(client):
    body = {"tenant_id": "empresa1", "provider": "c6",
            "account_config": {"chave_pix": "k"}, "pix": {"valor": "1.00"}}
    r = client.post("/pix", json=body, headers={"Authorization": "Bearer bapi_inexistente"})
    assert r.status_code == 401


def test_token_de_outro_tenant_403(client):
    token = _cadastrar(client, tenant="sistemaA")
    body = {"tenant_id": "sistemaB", "provider": "c6",
            "account_config": {"chave_pix": "k"}, "pix": {"valor": "1.00"}}
    r = client.post("/pix", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_revogacao_imediata(client, monkeypatch):
    token = _cadastrar(client)
    r = client.delete("/credenciais", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 204
    # token morto -> 401 nas rotas
    body = {"tenant_id": "empresa1", "provider": "c6",
            "account_config": {"chave_pix": "k"}, "pix": {"valor": "1.00"}}
    r = client.post("/pix", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    # revogar de novo -> 401
    assert client.delete("/credenciais", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_blob_adulterado_trata_como_invalido(client, tmp_path):
    token = _cadastrar(client)
    db = sqlite3.connect(str(tmp_path / "creds.db"))
    db.execute("UPDATE credential_tokens SET ciphertext = X'00112233'")
    db.commit()
    body = {"tenant_id": "empresa1", "provider": "c6",
            "account_config": {"chave_pix": "k"}, "pix": {"valor": "1.00"}}
    r = client.post("/pix", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401  # GCM InvalidTag -> token inválido, nunca 500


def test_bearer_tem_prioridade_sobre_corpo_e_vault(client, monkeypatch):
    monkeypatch.setenv("VAULT__empresa1__c6__client_id", "cid-vault")
    monkeypatch.setenv("VAULT__empresa1__c6__client_secret", "sv")
    token = _cadastrar(client)
    used = {}

    def fake_request(self, method, path, json=None, params=None):
        used["client_id"] = self.client_id
        return {"txid": "T", "status": "ATIVA"}

    monkeypatch.setattr("app.clients.oauth_mtls.OAuthMtlsClient.request", fake_request)

    body = {"tenant_id": "empresa1", "provider": "c6",
            "account_config": {"chave_pix": "k"}, "pix": {"valor": "1.00"},
            "credentials": {"client_id": "cid-corpo", "client_secret": "sc"}}
    r = client.post("/pix", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert used["client_id"] == "cid-token"  # bearer > corpo > vault


def test_postgres_usa_schema_proprio_nao_public(monkeypatch):
    # stub do psycopg: grava o SQL executado, sem rede/banco
    import sys, types

    executed = []

    class FakeCursor:
        rowcount = 1
        def fetchone(self): return None

    class FakeConn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql, params=None):
            executed.append(sql)
            return FakeCursor()

    fake = types.ModuleType("psycopg")
    fake.connect = lambda dsn: FakeConn()
    monkeypatch.setitem(sys.modules, "psycopg", fake)

    from app.core.credential_store import PostgresStore

    store = PostgresStore("postgresql://fake")
    assert any('CREATE SCHEMA IF NOT EXISTS "boleto_api"' in s for s in executed)
    assert any('"boleto_api".credential_tokens' in s for s in executed)
    assert not any("public.credential_tokens" in s for s in executed)

    store.put("h", "t", "c6", b"s", b"n", b"c")
    assert '"boleto_api".credential_tokens' in executed[-1]  # DML tambem qualificado

    # schema custom via env + validacao anti-injecao
    monkeypatch.setenv("CREDENTIAL_DB_SCHEMA", "meu_esquema")
    PostgresStore("postgresql://fake")
    assert any('"meu_esquema".credential_tokens' in s for s in executed)

    monkeypatch.setenv("CREDENTIAL_DB_SCHEMA", 'x"; DROP TABLE y;--')
    import pytest as _pytest
    with _pytest.raises(ValueError):
        PostgresStore("postgresql://fake")
