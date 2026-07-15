# Pix Automático (BACEN) + P_05 recebidos + P_06 webhook por chave.
# O dialeto é compartilhado (BacenPixAutomaticoMixin): testado em C6 e Sicoob.
import pytest


@pytest.fixture
def envs(monkeypatch):
    for t in ("empresa1",):
        for prov in ("c6", "sicoob"):
            monkeypatch.setenv(f"VAULT__{t}__{prov}__client_id", "cid")
            monkeypatch.setenv(f"VAULT__{t}__{prov}__client_secret", "sec")


def _capture(monkeypatch, response=None):
    calls = []

    def fake_request(self, method, path, json=None, params=None):
        calls.append({"method": method, "path": path, "json": json, "params": params})
        return response if response is not None else {"idRec": "RR1", "status": "CRIADA"}

    monkeypatch.setattr("app.clients.oauth_mtls.OAuthMtlsClient.request", fake_request)
    return calls


REC = {
    "contrato": "CT-2026-001", "objeto": "Aluguel Apto 101",
    "devedor": {"nome": "Jose", "documento": "12345678909"},
    "periodicidade": "MENSAL", "data_inicial": "2026-08-01",
    "valor_fixo": "1500.00", "politica_retentativa": "PERMITE_3R_7D",
}


def test_criar_recorrencia_mapeia_payload_bacen(client, envs, monkeypatch):
    calls = _capture(monkeypatch)
    body = {"tenant_id": "empresa1", "provider": "c6", "recorrencia": REC}
    r = client.post("/pix-automatico/recorrencias", json=body)
    assert r.status_code == 201, r.text
    sent = calls[0]["json"]
    assert calls[0] == {"method": "POST", "path": "/v2/pix/rec", "json": sent, "params": None}
    assert sent["vinculo"]["contrato"] == "CT-2026-001"
    assert sent["vinculo"]["devedor"] == {"nome": "Jose", "cpf": "12345678909"}
    assert sent["calendario"] == {"dataInicial": "2026-08-01", "periodicidade": "MENSAL"}
    assert sent["valor"] == {"valorRec": "1500.00"}
    assert sent["politicaRetentativa"] == "PERMITE_3R_7D"


def test_recorrencia_no_sicoob_mesmo_dialeto(client, envs, monkeypatch):
    calls = _capture(monkeypatch)
    body = {"tenant_id": "empresa1", "provider": "sicoob", "recorrencia": REC}
    assert client.post("/pix-automatico/recorrencias", json=body).status_code == 201
    assert calls[0]["path"] == "/pix/api/v2/rec"  # só muda o prefixo


def test_valor_fixo_xor_minimo(client, envs):
    body = {"tenant_id": "empresa1", "provider": "c6",
            "recorrencia": {**REC, "valor_minimo": "10.00"}}
    assert client.post("/pix-automatico/recorrencias", json=body).status_code == 422
    body = {"tenant_id": "empresa1", "provider": "c6",
            "recorrencia": {k: v for k, v in REC.items() if k != "valor_fixo"}}
    assert client.post("/pix-automatico/recorrencias", json=body).status_code == 422


def test_recorrencia_txid_ativacao_e_gestao(client, envs, monkeypatch):
    calls = _capture(monkeypatch)
    body = {"tenant_id": "empresa1", "provider": "c6",
            "recorrencia": {**REC, "txid_ativacao": "T" * 30}}
    client.post("/pix-automatico/recorrencias", json=body)
    assert calls[0]["json"]["ativacao"] == {"dadosJornada": {"txid": "T" * 30}}
    # gestão (Jornada 4): consulta, revisão/cancelamento, lista
    client.get("/pix-automatico/recorrencias/RR1", params={"tenant_id": "empresa1", "provider": "c6"})
    assert calls[1] == {"method": "GET", "path": "/v2/pix/rec/RR1", "json": None, "params": None}
    client.patch("/pix-automatico/recorrencias/RR1", params={"tenant_id": "empresa1", "provider": "c6"},
                 json={"status": "CANCELADA"})
    assert calls[2]["method"] == "PATCH" and calls[2]["json"] == {"status": "CANCELADA"}
    client.get("/pix-automatico/recorrencias", params={"tenant_id": "empresa1", "provider": "c6",
                                                       "inicio": "2026-07-01T00:00:00Z",
                                                       "fim": "2026-07-31T23:59:59Z"})
    assert calls[3]["path"] == "/v2/pix/rec"


def test_solicitacao_jornada1(client, envs, monkeypatch):
    calls = _capture(monkeypatch, {"idSolicRec": "S1"})
    body = {"tenant_id": "empresa1", "provider": "c6", "dados": {"idRec": "RR1"}}
    assert client.post("/pix-automatico/solicitacoes", json=body).status_code == 201
    assert calls[0] == {"method": "POST", "path": "/v2/pix/solicrec",
                        "json": {"idRec": "RR1"}, "params": None}
    client.get("/pix-automatico/solicitacoes/S1", params={"tenant_id": "empresa1", "provider": "c6"})
    assert calls[1]["path"] == "/v2/pix/solicrec/S1"


def test_cobranca_recorrente_jornada3(client, envs, monkeypatch):
    calls = _capture(monkeypatch, {"txid": "TX1", "status": "CRIADA"})
    body = {"tenant_id": "empresa1", "provider": "c6",
            "cobranca": {"id_rec": "RR1", "valor": "1500.00", "data_vencimento": "2026-08-05",
                         "info_adicional": "Aluguel 08/2026"}}
    r = client.put("/pix-automatico/cobrancas/TXID123", json=body)
    assert r.status_code == 201, r.text
    sent = calls[0]["json"]
    assert calls[0]["path"] == "/v2/pix/cobr/TXID123" and calls[0]["method"] == "PUT"
    assert sent == {"idRec": "RR1", "calendario": {"dataDeVencimento": "2026-08-05"},
                    "valor": {"original": "1500.00"}, "infoAdicional": "Aluguel 08/2026"}
    # retentativa pós-vencimento
    client.post("/pix-automatico/cobrancas/TXID123/retentativa/2026-08-08",
                params={"tenant_id": "empresa1", "provider": "c6"})
    assert calls[1]["path"] == "/v2/pix/cobr/TXID123/retentativa/2026-08-08"


def test_webhooks_pix_automatico(client, envs, monkeypatch):
    calls = _capture(monkeypatch, {})
    r = client.put("/pix-automatico/config/webhooks", params={"tenant_id": "empresa1", "provider": "c6"},
                   json={"url_recorrencia": "https://gw/webhooks/c6/empresa1",
                         "url_cobranca": "https://gw/webhooks/c6/empresa1"})
    assert r.status_code == 200, r.text
    assert calls[0]["path"] == "/v2/pix/webhookrec"
    assert calls[1]["path"] == "/v2/pix/webhookcobr"
    r = client.put("/pix-automatico/config/webhooks", params={"tenant_id": "empresa1", "provider": "c6"},
                   json={})
    assert r.status_code == 422


# --- P_05 Pix recebidos + P_06 webhook por chave -----------------------------------

def test_pix_recebidos_e_devolucao(client, envs, monkeypatch):
    calls = _capture(monkeypatch, {"pix": []})
    client.get("/pix/recebidos", params={"tenant_id": "empresa1", "provider": "c6",
                                         "inicio": "2026-07-01T00:00:00Z", "fim": "2026-07-31T23:59:59Z"})
    assert calls[0]["path"] == "/v2/pix/pix"
    client.get("/pix/recebidos/E2E123", params={"tenant_id": "empresa1", "provider": "c6"})
    assert calls[1]["path"] == "/v2/pix/pix/E2E123"
    r = client.put("/pix/recebidos/E2E123/devolucao/D1",
                   params={"tenant_id": "empresa1", "provider": "c6"}, json={"valor": "10.00"})
    assert r.status_code == 201
    assert calls[2] == {"method": "PUT", "path": "/v2/pix/pix/E2E123/devolucao/D1",
                        "json": {"valor": "10.00"}, "params": None}
    # sicoob: mesmo dialeto
    client.get("/pix/recebidos", params={"tenant_id": "empresa1", "provider": "sicoob",
                                         "inicio": "2026-07-01T00:00:00Z", "fim": "2026-07-31T23:59:59Z"})
    assert calls[3]["path"] == "/pix/api/v2/pix"


def test_webhook_pix_por_chave(client, envs, monkeypatch):
    calls = _capture(monkeypatch, {})
    r = client.put("/config/webhook-pix", json={
        "tenant_id": "empresa1", "provider": "c6", "chave": "minha-chave-evp",
        "url": "https://gw/webhooks/c6/empresa1"})
    assert r.status_code == 200, r.text
    assert calls[0] == {"method": "PUT", "path": "/v2/pix/webhook/minha-chave-evp",
                        "json": {"webhookUrl": "https://gw/webhooks/c6/empresa1"}, "params": None}
    client.get("/config/webhook-pix", params={"tenant_id": "empresa1", "provider": "c6",
                                              "chave": "minha-chave-evp"})
    assert calls[1]["method"] == "GET"
    client.delete("/config/webhook-pix", params={"tenant_id": "empresa1", "provider": "c6",
                                                 "chave": "minha-chave-evp"})
    assert calls[2]["method"] == "DELETE"
    assert client.put("/config/webhook-pix", json={"tenant_id": "empresa1"}).status_code == 422
