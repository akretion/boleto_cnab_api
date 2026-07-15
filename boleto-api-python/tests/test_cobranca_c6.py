import pytest

from app.providers.c6 import C6Provider, _map_status
from app.schemas import Status


@pytest.fixture
def c6_env(monkeypatch):
    monkeypatch.setenv("VAULT__empresa1__c6__client_id", "cid")
    monkeypatch.setenv("VAULT__empresa1__c6__client_secret", "sec")
    # cobrança registrada do C6 pronta (senão cai no fallback brcobrança)
    monkeypatch.setenv("C6_REGISTERED_READY", "true")
    # sem pfx -> contexto SSL default, não precisa de cert real no teste


def test_c6_status_mapping():
    assert _map_status("CREATED") == Status.registrado
    assert _map_status("PAID") == Status.liquidado
    assert _map_status("CANCELLED") == Status.baixado
    assert _map_status("???") is None


def test_c6_registrar_mapeia_payload_e_normaliza(client, cobranca_payload, c6_env, monkeypatch):
    captured = {}

    def fake_request(self, method, path, json=None, params=None):
        captured.update(method=method, path=path, json=json)
        # bank_slip_create_response (boleto-bancário.yaml)
        return {
            "id": "01J3NCKY6Q99QC4D7T733D35QD",
            "our_number": "3048",
            "digitable_line": "33690.00009 03048.720001 92241.282133 5 96900000012345",
            "bar_code": "33695969000000123450000003048720009224128213",
        }

    monkeypatch.setattr("app.clients.oauth_mtls.OAuthMtlsClient.request", fake_request)

    cobranca_payload["pagador"]["endereco"] = {
        "street": "Av. Nove de Julho", "number": 123,
        "city": "Rio de Janeiro", "state": "RJ", "zip_code": "05093000",
    }
    body = {
        "tenant_id": "empresa1",
        "provider": "c6",
        "account_config": {"billing_scheme": "21"},
        "cobranca": cobranca_payload,
    }
    r = client.post("/cobranca", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["id"] == "01J3NCKY6Q99QC4D7T733D35QD"
    assert data["status"] == "registrado"  # create não devolve status -> default
    assert data["linha_digitavel"].startswith("33690")

    # payload mapeado para o contrato REAL do C6 (bank_slip_create_request)
    assert captured["method"] == "POST"
    assert captured["path"] == "/v1/bank_slips/"
    sent = captured["json"]
    assert sent["external_reference_id"] == "A-1"
    assert sent["amount"] == 1000.0
    assert sent["due_date"] == "2026-07-10"
    assert sent["our_number"] == "123"
    assert sent["billing_scheme"] == "21"
    assert sent["payer"]["tax_id"] == "12345678901"
    assert sent["payer"]["address"]["zip_code"] == "05093000"


def test_c6_consultar_baixar_e_pdf(c6_env, monkeypatch):
    calls = []

    def fake_request(self, method, path, json=None, params=None):
        calls.append((method, path))
        if method == "GET":
            return {"id": "X", "status": "PAID", "base64_pdf_file": "JVBERi0="}
        return {}  # PUT /cancel -> 204 sem corpo

    monkeypatch.setattr("app.clients.oauth_mtls.OAuthMtlsClient.request", fake_request)
    p = C6Provider(account_config={}, credentials={"client_id": "c", "client_secret": "s"})

    assert p.consultar("X").status == Status.liquidado
    assert p.pdf("X").pdf_base64 == "JVBERi0="

    out = p.baixar("X")
    assert out.status == Status.baixado
    assert ("PUT", "/v1/bank_slips/X/cancel") in calls
