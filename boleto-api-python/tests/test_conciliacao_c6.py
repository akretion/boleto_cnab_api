# Conciliação C6 Pay (/v1/c6pay/statement) — recebíveis e transações.
import pytest


@pytest.fixture
def c6_env(monkeypatch):
    monkeypatch.setenv("VAULT__empresa1__c6__client_id", "cid")
    monkeypatch.setenv("VAULT__empresa1__c6__client_secret", "sec")


def test_recebiveis(client, c6_env, monkeypatch):
    captured = {}

    def fake_request(self, method, path, json=None, params=None):
        captured.update(method=method, path=path, params=params)
        return {
            "page": 1, "last_page": 3, "items": 120,
            "receivables": [
                {"receivable_id": "R1", "gross_amount": 100.0, "net_amount": 97.0, "expected_date": "2026-07-20"},
            ],
        }

    monkeypatch.setattr("app.clients.oauth_mtls.OAuthMtlsClient.request", fake_request)

    r = client.get("/conciliacao/recebiveis", params={
        "tenant_id": "empresa1", "provider": "c6",
        "start_date": "2026-07-01", "end_date": "2026-07-15", "page": 1, "size": 50,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["page"] == 1 and data["last_page"] == 3 and data["total_items"] == 120
    assert data["items"][0]["receivable_id"] == "R1"

    assert captured["path"] == "/v1/c6pay/statement/receivables"
    assert captured["params"] == {"start_date": "2026-07-01", "end_date": "2026-07-15", "page": 1, "size": 50}


def test_transacoes(client, c6_env, monkeypatch):
    monkeypatch.setattr(
        "app.clients.oauth_mtls.OAuthMtlsClient.request",
        lambda self, method, path, json=None, params=None: {
            "page": 1, "last-page": 1, "transactions": [{"id": "T1", "status": "APPROVED"}],
        },
    )
    r = client.get("/conciliacao/transacoes", params={
        "tenant_id": "empresa1", "provider": "c6", "start_date": "2026-07-01", "end_date": "2026-07-15",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["last_page"] == 1  # aceita o alias last-page do /transactions
    assert data["items"][0]["id"] == "T1"


def test_conciliacao_provider_brcobranca_retorna_422(client, c6_env):
    r = client.get("/conciliacao/recebiveis", params={
        "tenant_id": "empresa1", "provider": "brcobranca", "start_date": "2026-07-01", "end_date": "2026-07-15",
    })
    assert r.status_code == 422
