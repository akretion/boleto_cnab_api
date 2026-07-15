# Credenciais NO REQUEST (nada gravado no servidor) — corpo em POSTs, header em GETs.
import base64
import json


def _b64(d: dict) -> str:
    return base64.b64encode(json.dumps(d).encode()).decode()


def test_pix_com_credenciais_no_corpo_sem_vault(client, monkeypatch):
    # NENHUMA env VAULT__* — as credenciais vêm no request e vivem só em memória.
    used = {}

    def fake_request(self, method, path, json=None, params=None):
        used["client_id"] = self.client_id
        return {"txid": "T1", "status": "ATIVA"}

    monkeypatch.setattr("app.clients.oauth_mtls.OAuthMtlsClient.request", fake_request)

    body = {
        "tenant_id": "qualquer",
        "provider": "c6",
        "account_config": {"chave_pix": "k"},
        "pix": {"valor": "1.00"},
        "credentials": {"client_id": "cid-req", "client_secret": "sec-req"},
    }
    r = client.post("/pix", json=body)
    assert r.status_code == 200, r.text
    assert used["client_id"] == "cid-req"  # usou a credencial do request


def test_cobranca_com_credenciais_no_corpo(client, cobranca_payload, monkeypatch):
    monkeypatch.setenv("C6_REGISTERED_READY", "true")
    used = {}

    def fake_request(self, method, path, json=None, params=None):
        used["client_id"] = self.client_id
        return {"id": "B1", "digitable_line": "x"}

    monkeypatch.setattr("app.clients.oauth_mtls.OAuthMtlsClient.request", fake_request)

    body = {
        "tenant_id": "qualquer", "provider": "c6", "account_config": {},
        "cobranca": cobranca_payload,
        "credentials": {"client_id": "cid-req", "client_secret": "s"},
    }
    r = client.post("/cobranca", json=body)
    assert r.status_code == 200, r.text
    assert used["client_id"] == "cid-req"


def test_request_credentials_tem_prioridade_sobre_vault(client, monkeypatch):
    monkeypatch.setenv("VAULT__t1__c6__client_id", "cid-vault")
    monkeypatch.setenv("VAULT__t1__c6__client_secret", "s-vault")
    used = {}

    def fake_request(self, method, path, json=None, params=None):
        used["client_id"] = self.client_id
        return {"txid": "T", "status": "ATIVA"}

    monkeypatch.setattr("app.clients.oauth_mtls.OAuthMtlsClient.request", fake_request)

    body = {
        "tenant_id": "t1", "provider": "c6", "account_config": {"chave_pix": "k"},
        "pix": {"valor": "1.00"},
        "credentials": {"client_id": "cid-req", "client_secret": "s-req"},
    }
    assert client.post("/pix", json=body).status_code == 200
    assert used["client_id"] == "cid-req"  # request > cofre


def test_get_com_header_x_bank_credentials(client, monkeypatch):
    used = {}

    def fake_request(self, method, path, json=None, params=None):
        used["client_id"] = self.client_id
        return {"txid": "T9", "status": "CONCLUIDA"}

    monkeypatch.setattr("app.clients.oauth_mtls.OAuthMtlsClient.request", fake_request)

    r = client.get(
        "/pix/T9", params={"tenant_id": "t", "provider": "c6"},
        headers={"X-Bank-Credentials": _b64({"client_id": "cid-h", "client_secret": "s"})},
    )
    assert r.status_code == 200, r.text
    assert used["client_id"] == "cid-h"


def test_conciliacao_com_header(client, monkeypatch):
    monkeypatch.setattr(
        "app.clients.oauth_mtls.OAuthMtlsClient.request",
        lambda self, method, path, json=None, params=None: {"page": 1, "receivables": []},
    )
    r = client.get(
        "/conciliacao/recebiveis",
        params={"tenant_id": "t", "provider": "c6", "start_date": "2026-07-01", "end_date": "2026-07-10"},
        headers={"X-Bank-Credentials": _b64({"client_id": "c", "client_secret": "s"})},
    )
    assert r.status_code == 200, r.text


def test_header_invalido_retorna_422(client):
    r = client.get(
        "/pix/T1", params={"tenant_id": "t", "provider": "c6"},
        headers={"X-Bank-Credentials": "nao-e-base64!!!"},
    )
    assert r.status_code == 422
    assert "X-Bank-Credentials" in r.json()["detail"]


def test_sem_credenciais_e_sem_vault_retorna_424(client):
    body = {"tenant_id": "ghost2", "provider": "c6", "account_config": {"chave_pix": "k"}, "pix": {"valor": "1.00"}}
    assert client.post("/pix", json=body).status_code == 424
