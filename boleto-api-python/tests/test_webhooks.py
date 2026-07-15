def test_webhook_c6_normaliza(client):
    r = client.post("/webhooks/c6", json={"id": "C6-1", "status": "PAID"})
    assert r.status_code == 200
    data = r.json()
    assert data["event"] == "cobranca.atualizada"
    assert data["id"] == "C6-1"
    assert data["status"] == "liquidado"


def test_webhook_sicoob_normaliza_pix(client):
    r = client.post("/webhooks/sicoob", json={"txid": "abc123", "valor": "50.00"})
    assert r.status_code == 200
    data = r.json()
    assert data["event"] == "pix.recebido"
    assert data["id"] == "abc123"
    assert data["status"] == "liquidado"


def test_webhook_banco_desconhecido_ignora(client):
    r = client.post("/webhooks/itau", json={"x": 1})
    assert r.status_code == 200
    assert r.json()["event"] == "ignorado"


def test_webhook_c6_faz_push_do_evento(client, monkeypatch):
    capturado = {}

    def fake_forward(event, *, url=None, secret=None):
        capturado.update(event)
        return True

    monkeypatch.setattr("app.routers.webhooks.forward_event", fake_forward)

    r = client.post("/webhooks/c6", json={"id": "C6-7", "status": "PAID"})
    assert r.status_code == 200
    # o evento normalizado foi encaminhado ao consumidor
    assert capturado["id"] == "C6-7"
    assert capturado["status"] == "liquidado"


def test_webhook_c6_pix_normaliza_por_txid(client):
    r = client.post("/webhooks/c6", json={"txid": "TX9", "status": "CONCLUIDA"})
    assert r.status_code == 200
    data = r.json()
    assert data["event"] == "pix.atualizada"
    assert data["id"] == "TX9"
    assert data["status"] == "liquidado"


def test_webhook_token_valida_quando_configurado(client, monkeypatch):
    monkeypatch.setenv("WEBHOOK_TOKEN__C6", "s3gr3do")

    # sem token -> 401 (nada é encaminhado)
    assert client.post("/webhooks/c6", json={"id": "1", "status": "PAID"}).status_code == 401
    # token errado -> 401
    r = client.post("/webhooks/c6?token=errado", json={"id": "1", "status": "PAID"})
    assert r.status_code == 401
    # token certo (query) -> 200
    r = client.post("/webhooks/c6?token=s3gr3do", json={"id": "1", "status": "PAID"})
    assert r.status_code == 200
    # token certo (header) -> 200
    r = client.post("/webhooks/c6", json={"id": "1", "status": "PAID"},
                    headers={"x-webhook-token": "s3gr3do"})
    assert r.status_code == 200


def test_webhook_sem_token_configurado_aceita(client):
    # opt-in: sem WEBHOOK_TOKEN__<BANCO>, comportamento anterior (aceita)
    assert client.post("/webhooks/c6", json={"id": "1", "status": "PAID"}).status_code == 200


def test_webhook_por_tenant_roteia_para_o_consumidor_dono(client, monkeypatch):
    monkeypatch.setenv("SUB__sistemaA__URL", "https://sistema-1.test/hook")
    monkeypatch.setenv("SUB__sistemaA__SECRET", "segA")
    destino = {}

    def fake_forward(event, *, url=None, secret=None):
        destino["url"] = url
        destino["secret"] = secret
        return True

    monkeypatch.setattr("app.routers.webhooks.forward_event", fake_forward)

    r = client.post("/webhooks/c6/sistemaA", json={"id": "C6-9", "status": "PAID"})
    assert r.status_code == 200
    assert destino == {"url": "https://sistema-1.test/hook", "secret": "segA"}


def test_webhook_c6_pix_automatico_normaliza(client):
    r = client.post("/webhooks/c6", json={"idRec": "RR1", "status": "ATIVA"})
    assert r.json()["event"] == "pix_automatico.recorrencia"
    r = client.post("/webhooks/c6", json={"idRec": "RR1", "txid": "TX1", "status": "CONCLUIDA"})
    data = r.json()
    assert data["event"] == "pix_automatico.cobranca"
    assert data["status"] == "liquidado"
