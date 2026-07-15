# Pix dinâmico C6 (/v2/pix, padrão BACEN) — cob imediata, cobv e consulta.
import pytest

from app.providers.c6 import _map_pix_status
from app.schemas import Status


@pytest.fixture
def c6_env(monkeypatch):
    monkeypatch.setenv("VAULT__empresa1__c6__client_id", "cid")
    monkeypatch.setenv("VAULT__empresa1__c6__client_secret", "sec")


def test_pix_status_mapping():
    assert _map_pix_status("ATIVA") == Status.registrado
    assert _map_pix_status("CONCLUIDA") == Status.liquidado
    assert _map_pix_status("REMOVIDA_PELO_USUARIO_RECEBEDOR") == Status.baixado
    assert _map_pix_status("REMOVIDA_PELO_PSP") == Status.baixado
    assert _map_pix_status(None) is None


def test_pix_cob_imediata(client, c6_env, monkeypatch):
    captured = {}

    def fake_request(self, method, path, json=None, params=None):
        captured.update(method=method, path=path, json=json)
        return {
            "txid": "TX123456789012345678901234567",
            "status": "ATIVA",
            "pixCopiaECola": "00020126580014br.gov.bcb.pix...",
            "loc": {"location": "pix.example.com/qr/9d36b84f"},
        }

    monkeypatch.setattr("app.clients.oauth_mtls.OAuthMtlsClient.request", fake_request)

    body = {
        "tenant_id": "empresa1",
        "provider": "c6",
        "account_config": {"chave_pix": "chave@empresa.com"},
        "pix": {"valor": "10.00", "expiracao_segundos": 1800, "descricao": "Pedido 42"},
    }
    r = client.post("/pix", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["txid"].startswith("TX")
    assert data["status"] == "registrado"
    assert data["pix_copia_cola"].startswith("00020126")
    assert data["location"].startswith("pix.example.com")

    # payload BACEN da cob imediata
    assert captured["method"] == "POST"
    assert captured["path"] == "/v2/pix/cob"
    sent = captured["json"]
    assert sent["valor"]["original"] == "10.00"
    assert sent["chave"] == "chave@empresa.com"  # veio do account_config
    assert sent["calendario"] == {"expiracao": 1800}
    assert sent["solicitacaoPagador"] == "Pedido 42"


def test_pix_cobv_com_vencimento(client, c6_env, monkeypatch):
    captured = {}

    def fake_request(self, method, path, json=None, params=None):
        captured.update(method=method, path=path, json=json)
        return {"txid": "A" * 30, "status": "ATIVA"}

    monkeypatch.setattr("app.clients.oauth_mtls.OAuthMtlsClient.request", fake_request)

    body = {
        "tenant_id": "empresa1",
        "provider": "c6",
        "account_config": {"chave_pix": "chave@empresa.com"},
        "pix": {
            "valor": "150.00",
            "txid": "A" * 30,
            "data_vencimento": "2026-08-31",
            "validade_apos_vencimento": 15,
            "devedor": {
                "nome": "Francisco da Silva",
                "documento": "12345678909",
                "endereco": {"logradouro": "Alameda Souza, 80", "cidade": "Recife", "uf": "PE", "cep": "70011750"},
            },
        },
    }
    r = client.post("/pix", json=body)
    assert r.status_code == 200, r.text

    # cobv: PUT /cobv/{txid} com calendario de vencimento e devedor completo
    assert captured["method"] == "PUT"
    assert captured["path"] == f"/v2/pix/cobv/{'A' * 30}"
    sent = captured["json"]
    assert sent["calendario"] == {"dataDeVencimento": "2026-08-31", "validadeAposVencimento": 15}
    assert sent["devedor"]["cpf"] == "12345678909"
    assert sent["devedor"]["uf"] == "PE"


def test_pix_consultar(client, c6_env, monkeypatch):
    monkeypatch.setattr(
        "app.clients.oauth_mtls.OAuthMtlsClient.request",
        lambda self, method, path, json=None, params=None: {"txid": "TX1", "status": "CONCLUIDA"},
    )
    r = client.get("/pix/TX1", params={"tenant_id": "empresa1", "provider": "c6"})
    assert r.status_code == 200
    assert r.json()["status"] == "liquidado"


def test_pix_sem_chave_retorna_422(client, c6_env):
    body = {"tenant_id": "empresa1", "provider": "c6", "account_config": {}, "pix": {"valor": "10.00"}}
    r = client.post("/pix", json=body)
    assert r.status_code == 422
    assert "chave" in r.json()["detail"]


def test_pix_provider_brcobranca_retorna_422(client, c6_env):
    # Pix dinâmico não existe offline — contrato explícito, sem fallback.
    body = {"tenant_id": "empresa1", "provider": "brcobranca", "account_config": {}, "pix": {"valor": "10.00"}}
    r = client.post("/pix", json=body)
    assert r.status_code == 422


def test_pix_multi_tenant_resolve_credencial_do_tenant(client, monkeypatch):
    monkeypatch.setenv("VAULT__t1__c6__client_id", "cid-t1")
    monkeypatch.setenv("VAULT__t1__c6__client_secret", "s1")
    monkeypatch.setenv("VAULT__t2__c6__client_id", "cid-t2")
    monkeypatch.setenv("VAULT__t2__c6__client_secret", "s2")
    used = []

    def fake_request(self, method, path, json=None, params=None):
        used.append(self.client_id)
        return {"txid": "T", "status": "ATIVA"}

    monkeypatch.setattr("app.clients.oauth_mtls.OAuthMtlsClient.request", fake_request)

    for tenant in ("t1", "t2"):
        body = {
            "tenant_id": tenant, "provider": "c6",
            "account_config": {"chave_pix": "k"}, "pix": {"valor": "1.00"},
        }
        assert client.post("/pix", json=body).status_code == 200

    assert used == ["cid-t1", "cid-t2"]  # cada tenant com a própria credencial


def test_pix_tenant_sem_credencial_retorna_424(client):
    body = {"tenant_id": "ghost", "provider": "c6", "account_config": {"chave_pix": "k"}, "pix": {"valor": "1.00"}}
    r = client.post("/pix", json=body)
    assert r.status_code == 424
