# Catálogo /bancos + autenticação unificada entre os bancos.


def test_bancos_lista_capacidades_reais(client):
    r = client.get("/bancos")
    assert r.status_code == 200
    data = r.json()
    bancos = {b["id"]: b for b in data["bancos"]}
    assert set(bancos) == {"c6", "sicoob", "brcobranca"}

    # capacidades refletem o código (introspecção)
    assert "pix_automatico" in bancos["c6"]["capacidades"]
    assert "pix_automatico" in bancos["sicoob"]["capacidades"]
    assert "bolepix" in bancos["c6"]["capacidades"]
    assert "bolepix" not in bancos["sicoob"]["capacidades"]  # exclusivo C6
    assert "extrato" in bancos["sicoob"]["capacidades"]      # paridade nova
    assert "carne" in bancos["brcobranca"]["capacidades"]
    assert len(bancos["brcobranca"]["bancos_cnab"]) == 18

    # mecanismo da API é único (bapi_); o ESQUEMA de credenciais é próprio por banco
    assert "bapi_" in data["autenticacao_api"]["cadastro"]
    assert "pfx_base64" in bancos["c6"]["credentials"]          # esquema C6
    assert "access_token" in bancos["sicoob"]["credentials"]     # esquema Sicoob
    assert bancos["c6"]["credentials"] != bancos["sicoob"]["credentials"]


def test_mecanismo_da_api_igual_nos_dois_bancos(client, monkeypatch):
    """O mecanismo (recebe -> armazena -> Bearer bapi_) é o MESMO nos 2 bancos,
    ainda que cada banco tenha o próprio esquema de parâmetros."""
    chamadas = []

    def fake_request(self, method, path, json=None, params=None):
        chamadas.append({"path": path, "token": self.token()})
        return {"txid": "T", "status": "ATIVA", "pixCopiaECola": "000201..."}

    monkeypatch.setattr("app.clients.oauth_mtls.OAuthMtlsClient.request", fake_request)

    for prov in ("c6", "sicoob"):
        body = {"tenant_id": "t", "provider": prov,
                "account_config": {"chave_pix": "k"}, "pix": {"valor": "1.00"},
                "credentials": {"client_id": "cid", "access_token": "tok-estatico-sandbox"}}
        r = client.post("/pix", json=body)
        assert r.status_code == 200, (prov, r.text)

    # o token estático foi usado direto (sem fluxo OAuth) em AMBOS
    assert [c["token"] for c in chamadas] == ["tok-estatico-sandbox"] * 2


def test_extrato_sicoob_mapeia_mes_ano(client, monkeypatch):
    monkeypatch.setenv("VAULT__t__sicoob__client_id", "cid")
    monkeypatch.setenv("VAULT__t__sicoob__client_secret", "s")
    captured = {}

    def fake_request(self, method, path, json=None, params=None):
        captured.update(path=path, params=params)
        return {"resultado": {"saldoAtual": "100.00"}}

    monkeypatch.setattr("app.clients.oauth_mtls.OAuthMtlsClient.request", fake_request)

    r = client.get("/extrato", params={"tenant_id": "t", "provider": "sicoob",
                                       "start_date": "2026-07-01", "end_date": "2026-07-15"})
    assert r.status_code == 200, r.text
    assert captured["path"] == "/conta-corrente/v4/extrato/7/2026"
    assert captured["params"]["diaInicial"] == 1 and captured["params"]["diaFinal"] == 15

    # multi-mês -> 422 com mensagem clara
    r = client.get("/extrato", params={"tenant_id": "t", "provider": "sicoob",
                                       "start_date": "2026-06-15", "end_date": "2026-07-15"})
    assert r.status_code == 422
    assert "mesmo mês" in r.json()["detail"]
