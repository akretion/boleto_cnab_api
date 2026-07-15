import httpx
import respx

from app.clients import engine


@respx.mock
def test_carne_registra_parcelas_e_monta_pdf(client, cobranca_payload, monkeypatch):
    # credenciais do tenant no cofre (pfx vazio -> contexto SSL default)
    monkeypatch.setenv("VAULT__empresa1__c6__client_id", "cid")
    monkeypatch.setenv("VAULT__empresa1__c6__client_secret", "sec")
    monkeypatch.setenv("C6_REGISTERED_READY", "true")  # usa o fluxo registrado
    monkeypatch.setattr(engine, "engine_url", lambda: "http://engine.test")

    # cada parcela registrada no banco devolve um nosso_numero
    counter = {"n": 0}

    def fake_request(self, method, path, json=None):
        counter["n"] += 1
        return {"id": f"C6-{counter['n']}", "status": "REGISTERED", "digitableLine": "00190..."}

    monkeypatch.setattr("app.clients.oauth_mtls.OAuthMtlsClient.request", fake_request)

    carne_route = respx.post("http://engine.test/api/render/carne").mock(
        return_value=httpx.Response(200, json={"pdf_base64": "JVBERi0xCg=="})
    )

    body = {
        "tenant_id": "empresa1",
        "provider": "c6",
        "account_config": {"agencia": "0001", "conta": "123"},
        "bank": "banco_c6",
        "parcelas": [cobranca_payload, {**cobranca_payload, "nosso_numero": "2"}],
    }
    r = client.post("/carne", json=body)
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["carne_pdf_base64"] == "JVBERi0xCg=="
    assert len(data["cobrancas"]) == 2
    assert [c["id"] for c in data["cobrancas"]] == ["C6-1", "C6-2"]

    # o render recebeu 2 boletos com o nosso_numero registrado pelo banco
    sent = carne_route.calls.last.request
    assert b'"bank":"banco_c6"' in sent.content.replace(b" ", b"")
    assert b'"nosso_numero":"C6-1"' in sent.content.replace(b" ", b"")
