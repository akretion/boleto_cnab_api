# Cobertura das operações do roteiro de homologação C6 (v3.0) adicionadas ao provider.
import pytest

from app.providers.c6 import C6Provider, ProcessamentoPendente
from app.schemas import Status


@pytest.fixture
def c6_env(monkeypatch):
    monkeypatch.setenv("VAULT__empresa1__c6__client_id", "cid")
    monkeypatch.setenv("VAULT__empresa1__c6__client_secret", "sec")
    monkeypatch.setenv("C6_REGISTERED_READY", "true")


def _capture(monkeypatch, response=None):
    calls = []

    def fake_request(self, method, path, json=None, params=None):
        calls.append({"method": method, "path": path, "json": json, "params": params})
        return response or {}

    monkeypatch.setattr("app.clients.oauth_mtls.OAuthMtlsClient.request", fake_request)
    return calls


# --- B_04 alteração ---------------------------------------------------------

def test_alterar_boleto(client, c6_env, monkeypatch):
    calls = _capture(monkeypatch, {"id": "X", "amount": 175.5})
    r = client.put("/cobranca/X", params={"tenant_id": "empresa1", "provider": "c6"},
                   json={"amount": 175.5})
    assert r.status_code == 200, r.text
    assert calls[0]["method"] == "PUT" and calls[0]["path"] == "/v1/bank_slips/X"
    assert calls[0]["json"] == {"amount": 175.5}


# --- P_01_01 cob com txid / P_01_03 revisar / P_01_05 lista / cobv ------------

def test_pix_cob_com_txid_usa_put(client, c6_env, monkeypatch):
    calls = _capture(monkeypatch, {"txid": "T" * 28, "status": "ATIVA"})
    body = {"tenant_id": "empresa1", "provider": "c6",
            "account_config": {"chave_pix": "k"},
            "pix": {"valor": "10.00", "txid": "T" * 28}}
    assert client.post("/pix", json=body).status_code == 200
    assert calls[0]["method"] == "PUT" and calls[0]["path"] == f"/v2/pix/cob/{'T'*28}"


def test_pix_revisar_patch(client, c6_env, monkeypatch):
    calls = _capture(monkeypatch, {"txid": "T1", "status": "ATIVA"})
    r = client.patch("/pix/T1", params={"tenant_id": "empresa1", "provider": "c6"},
                     json={"valor": {"original": "12.34"}})
    assert r.status_code == 200, r.text
    assert calls[0]["method"] == "PATCH" and calls[0]["path"] == "/v2/pix/cob/T1"
    # cobv
    r = client.patch("/pix/T1", params={"tenant_id": "empresa1", "provider": "c6", "vencimento": "true"},
                     json={"valor": {"original": "160.00"}})
    assert calls[1]["path"] == "/v2/pix/cobv/T1"


def test_pix_consultar_cobv(client, c6_env, monkeypatch):
    calls = _capture(monkeypatch, {"txid": "T2", "status": "ATIVA"})
    r = client.get("/pix/T2", params={"tenant_id": "empresa1", "provider": "c6", "vencimento": "true"})
    assert r.status_code == 200
    assert calls[0]["path"] == "/v2/pix/cobv/T2"


def test_pix_listar_periodo(client, c6_env, monkeypatch):
    calls = _capture(monkeypatch, {"cobs": []})
    r = client.get("/pix", params={"tenant_id": "empresa1", "provider": "c6",
                                   "inicio": "2026-07-01T00:00:00Z", "fim": "2026-07-15T23:59:59Z"})
    assert r.status_code == 200
    assert calls[0]["path"] == "/v2/pix/cob"
    assert calls[0]["params"] == {"inicio": "2026-07-01T00:00:00Z", "fim": "2026-07-15T23:59:59Z"}
    client.get("/pix", params={"tenant_id": "empresa1", "provider": "c6", "vencimento": "true",
                               "inicio": "2026-07-01T00:00:00Z", "fim": "2026-07-15T23:59:59Z"})
    assert calls[1]["path"] == "/v2/pix/cobv"


# --- P_03 lote cobv -----------------------------------------------------------

def test_lote_cobv(client, c6_env, monkeypatch):
    calls = _capture(monkeypatch, {"descricao": "Lote", "cobsv": []})
    body = {"tenant_id": "empresa1", "provider": "c6",
            "account_config": {"chave_pix": "k"},
            "descricao": "Lote",
            "cobrancas": [{"valor": "10.00", "txid": "A" * 30, "data_vencimento": "2026-08-31",
                           "devedor": {"nome": "F", "documento": "12345678909",
                                       "endereco": {"logradouro": "Rua X", "cidade": "R",
                                                    "uf": "PE", "cep": "50000000"}}}]}
    r = client.put("/pix/lote/123", json=body)
    assert r.status_code == 200, r.text
    assert calls[0]["method"] == "PUT" and calls[0]["path"] == "/v2/pix/lotecobv/123"
    item = calls[0]["json"]["cobsv"][0]
    assert item["txid"] == "A" * 30 and item["chave"] == "k"
    assert client.get("/pix/lote/123", params={"tenant_id": "empresa1", "provider": "c6"}).status_code == 200
    assert calls[1]["method"] == "GET"
    r = client.get("/pix/lotes", params={"tenant_id": "empresa1", "provider": "c6",
                                         "inicio": "2026-07-01T00:00:00Z", "fim": "2026-07-15T23:59:59Z"})
    assert r.status_code == 200


# --- E_01 extrato ---------------------------------------------------------------

def test_extrato(client, c6_env, monkeypatch):
    calls = _capture(monkeypatch, {"statements": []})
    r = client.get("/extrato", params={"tenant_id": "empresa1", "provider": "c6",
                                       "start_date": "2026-06-15", "end_date": "2026-07-15"})
    assert r.status_code == 200, r.text
    assert calls[0]["path"] == "/v1/statement/"
    assert calls[0]["params"] == {"start_date": "2026-06-15", "end_date": "2026-07-15"}


# --- B_07 webhook no banco -------------------------------------------------------

def test_webhook_banco_cadastro_consulta_remocao(client, c6_env, monkeypatch):
    calls = _capture(monkeypatch, {"url": "https://x/webhooks/c6", "service": "BANK_SLIP"})
    body = {"tenant_id": "empresa1", "provider": "c6",
            "url": "https://x/webhooks/c6", "service": "BANK_SLIP"}
    assert client.post("/config/webhook-banco", json=body).status_code == 200
    assert calls[0] == {"method": "POST", "path": "/v1/webhooks/",
                        "json": {"url": "https://x/webhooks/c6", "service": "BANK_SLIP"}, "params": None}
    assert client.get("/config/webhook-banco",
                      params={"tenant_id": "empresa1", "provider": "c6"}).status_code == 200
    assert client.delete("/config/webhook-banco",
                         params={"tenant_id": "empresa1", "provider": "c6"}).status_code == 200
    assert calls[2]["method"] == "DELETE"


# --- Bolepix ----------------------------------------------------------------------

def test_bolepix_criar_mapeia_schema_v2(client, c6_env, monkeypatch):
    calls = _capture(monkeypatch, {
        "external_reference_id": "A" * 26, "status": "CREATED",
        "payment_method": {"bank_slip": {"digitable_line": "336x", "bar_code": "336y"},
                           "pix": {"qr_code": "00020126..."}},
    })
    body = {"tenant_id": "empresa1", "provider": "c6",
            "account_config": {"chave_pix": "evp-key", "billing_scheme": "21"},
            "bolepix": {"valor": "99.90", "vencimento": "2026-08-31",
                        "descricao": "Pedido 42",
                        "pagador": {"nome": "Jose", "documento": "12345678909",
                                    "endereco": {"street": "Av. X", "number": 100,
                                                 "bairro": "Centro", "city": "SP",
                                                 "state": "SP", "zip_code": "01000000"}}}}
    r = client.post("/bolepix", json=body)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["linha_digitavel"] == "336x"
    assert data["pix_copia_cola"].startswith("00020126")
    sent = calls[0]["json"]
    import re
    assert re.fullmatch(r"[A-Z0-9]{26}", sent["external_reference_id"])  # gerado
    assert sent["payer"]["address"]["address"] == "Av. X, 100"  # rua+numero unificados
    assert sent["payer"]["address"]["neighborhood"] == "Centro"
    assert sent["payment_method"]["pix"] == {"key": "evp-key", "type": "EVP"}
    assert sent["description"] == "Pedido 42"


def test_bolepix_consultar_pdf_cancelar(client, c6_env, monkeypatch):
    calls = _capture(monkeypatch, {"external_reference_id": "B" * 26, "status": "CREATED",
                                   "base64_pdf_file": "JVBERi0="})
    ext = "B" * 26
    assert client.get(f"/bolepix/{ext}", params={"tenant_id": "empresa1", "provider": "c6"}).status_code == 200
    r = client.get(f"/bolepix/{ext}/pdf", params={"tenant_id": "empresa1", "provider": "c6"})
    assert r.json()["pdf_base64"] == "JVBERi0="
    r = client.delete(f"/bolepix/{ext}", params={"tenant_id": "empresa1", "provider": "c6"})
    assert r.status_code == 200
    assert calls[-1]["path"] == f"/v2/bank_slips/{ext}/cancel"


# --- retry CIP (assincronia aprendida no sandbox) -----------------------------------

def test_cancel_cip_pendente_vira_409(client, c6_env, monkeypatch):
    import httpx

    monkeypatch.setenv("VAULT__empresa1__c6__pfx_base64", "")
    monkeypatch.setattr("app.providers.c6.C6_CIP_RETRIES", 2)
    monkeypatch.setattr("app.providers.c6.C6_CIP_WAIT", 0.01)

    def fake_request(self, method, path, json=None, params=None):
        req = httpx.Request(method, "https://x" + path)
        resp = httpx.Response(422, request=req,
                              text='{"detail":"já existe uma requisição à CIP sujeita a aprovação"}')
        raise httpx.HTTPStatusError("422", request=req, response=resp)

    monkeypatch.setattr("app.clients.oauth_mtls.OAuthMtlsClient.request", fake_request)
    r = client.delete("/cobranca/X", params={"tenant_id": "empresa1", "provider": "c6"})
    assert r.status_code == 409
    assert "processamento" in r.json()["detail"]


def test_cancel_cip_resolve_apos_retry(c6_env, monkeypatch):
    import httpx

    monkeypatch.setattr("app.providers.c6.C6_CIP_WAIT", 0.01)
    tries = {"n": 0}

    def fake_request(self, method, path, json=None, params=None):
        tries["n"] += 1
        if tries["n"] < 3:
            req = httpx.Request(method, "https://x" + path)
            resp = httpx.Response(400, request=req, text="já existe uma requisição em processamento")
            raise httpx.HTTPStatusError("400", request=req, response=resp)
        return {}

    monkeypatch.setattr("app.clients.oauth_mtls.OAuthMtlsClient.request", fake_request)
    p = C6Provider(account_config={}, credentials={"client_id": "c", "client_secret": "s"})
    assert p.baixar("X").status == Status.baixado
    assert tries["n"] == 3
