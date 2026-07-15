import httpx
import respx

from app.providers import brcobranca_proxy
from app.registry import registered_ready
from app.schemas import Provider


def test_registered_ready_default_false(monkeypatch):
    monkeypatch.delenv("C6_REGISTERED_READY", raising=False)
    monkeypatch.delenv("SICOOB_REGISTERED_READY", raising=False)
    assert registered_ready(Provider.c6) is False
    assert registered_ready(Provider.sicoob) is False
    assert registered_ready(Provider.brcobranca) is True


def test_registered_ready_liga_por_env(monkeypatch):
    monkeypatch.setenv("C6_REGISTERED_READY", "true")
    assert registered_ready(Provider.c6) is True


@respx.mock
def test_c6_nao_pronto_cai_no_brcobranca(client, cobranca_payload, monkeypatch):
    # C6 não homologado e SEM credenciais no cofre: deve cair no método antigo
    # (brcobrança offline) e ainda assim registrar com sucesso.
    monkeypatch.delenv("C6_REGISTERED_READY", raising=False)
    monkeypatch.setattr(brcobranca_proxy, "ENGINE_URL", "http://engine.test")
    route = respx.post("http://engine.test/api/render/boleto").mock(
        return_value=httpx.Response(200, json={
            "nosso_numero": "1", "linha_digitavel": "00190.00009 ...", "codigo_barras": "0019",
        })
    )

    body = {
        "tenant_id": "tenant_sem_credencial",
        "provider": "c6",
        "account_config": {},  # bank é injetado (banco_c6) pelo fallback
        "cobranca": cobranca_payload,
    }
    r = client.post("/cobranca", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "registrado"
    assert data["linha_digitavel"].startswith("00190")
    # roteou para o engine com o banco do brcobrança
    assert b'"bank":"banco_c6"' in route.calls.last.request.content.replace(b" ", b"")


@respx.mock
def test_sicoob_nao_pronto_cai_no_brcobranca(client, cobranca_payload, monkeypatch):
    monkeypatch.delenv("SICOOB_REGISTERED_READY", raising=False)
    monkeypatch.setattr(brcobranca_proxy, "ENGINE_URL", "http://engine.test")
    route = respx.post("http://engine.test/api/render/boleto").mock(
        return_value=httpx.Response(200, json={"nosso_numero": "7", "linha_digitavel": "75691..."})
    )
    body = {"tenant_id": "x", "provider": "sicoob", "account_config": {}, "cobranca": cobranca_payload}
    r = client.post("/cobranca", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "registrado"
    assert b'"bank":"sicoob"' in route.calls.last.request.content.replace(b" ", b"")


@respx.mock
def test_provider_omitido_ou_vazio_vai_para_brcobranca(client, cobranca_payload, monkeypatch):
    # Contrato: provider ausente/"" roteia para o método antigo (CNAB offline).
    monkeypatch.setattr(brcobranca_proxy, "ENGINE_URL", "http://engine.test")
    respx.post("http://engine.test/api/render/boleto").mock(
        return_value=httpx.Response(200, json={"nosso_numero": "7", "linha_digitavel": "x", "codigo_barras": "y"})
    )

    sem_provider = {
        "tenant_id": "t", "account_config": {"bank": "banco_c6"}, "cobranca": cobranca_payload,
    }
    r = client.post("/cobranca", json=sem_provider)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == "7"

    vazio = {**sem_provider, "provider": ""}
    r = client.post("/cobranca", json=vazio)
    assert r.status_code == 200, r.text
