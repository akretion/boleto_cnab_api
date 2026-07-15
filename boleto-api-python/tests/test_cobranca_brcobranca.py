import httpx
import respx

from app.providers import brcobranca_proxy


@respx.mock
def test_brcobranca_proxy_registra_via_engine(client, cobranca_payload, monkeypatch):
    monkeypatch.setattr(brcobranca_proxy, "ENGINE_URL", "http://engine.test")
    route = respx.post("http://engine.test/api/render/boleto").mock(
        return_value=httpx.Response(
            200,
            json={
                "nosso_numero": "123",
                "linha_digitavel": "00190.00009 ...",
                "codigo_barras": "0019...",
                "pdf_base64": "JVBER...",
            },
        )
    )

    body = {
        "tenant_id": "empresa1",
        "provider": "brcobranca",
        "account_config": {"bank": "itau", "agencia": "1234", "conta_corrente": "56789"},
        "cobranca": cobranca_payload,
    }
    r = client.post("/cobranca", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "registrado"
    assert data["linha_digitavel"].startswith("00190")
    assert data["pdf_base64"] == "JVBER..."

    # o engine recebeu bank + dados mapeados
    sent = route.calls.last.request
    assert b'"bank":"itau"' in sent.content.replace(b" ", b"")
    assert b'"valor":1000' in sent.content.replace(b" ", b"")


@respx.mock
def test_brcobranca_proxy_propaga_erro_do_engine(client, cobranca_payload, monkeypatch):
    monkeypatch.setattr(brcobranca_proxy, "ENGINE_URL", "http://engine.test")
    respx.post("http://engine.test/api/render/boleto").mock(
        return_value=httpx.Response(400, text="dados invalidos")
    )
    body = {
        "tenant_id": "empresa1",
        "provider": "brcobranca",
        "account_config": {"bank": "itau"},
        "cobranca": cobranca_payload,
    }
    r = client.post("/cobranca", json=body)
    assert r.status_code == 200
    assert r.json()["status"] == "erro"
