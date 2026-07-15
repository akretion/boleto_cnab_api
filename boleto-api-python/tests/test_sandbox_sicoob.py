# E2E contra o SANDBOX do Sicoob — roda só com credenciais no ambiente.
#
# O sandbox do Sicoob (developers.sicoob.com.br) usa TOKEN ESTÁTICO do portal
# (sem mTLS). Requisitos (nunca commitar valores):
#   SICOOB_SANDBOX_TOKEN       token do portal (obrigatório)
#   SICOOB_SANDBOX_CLIENT_ID   client_id do app no portal (obrigatório)
#   SICOOB_SANDBOX_BASE_URL    default https://sandbox.sicoob.com.br/sicoob/sandbox
#   SICOOB_SANDBOX_NUMERO_CLIENTE / SICOOB_SANDBOX_CHAVE_PIX (opcionais)
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    not (os.environ.get("SICOOB_SANDBOX_TOKEN") and os.environ.get("SICOOB_SANDBOX_CLIENT_ID")),
    reason="sem credenciais SICOOB_SANDBOX_* no ambiente",
)


@pytest.fixture
def provider(monkeypatch):
    # SICOOB_BASE é resolvido no import do módulo — patcheia o atributo direto
    base = os.environ.get("SICOOB_SANDBOX_BASE_URL",
                          "https://sandbox.sicoob.com.br/sicoob/sandbox")
    monkeypatch.setattr("app.providers.sicoob.SICOOB_BASE", base)
    from app.providers.sicoob import SicoobProvider

    return SicoobProvider(
        account_config={
            "numeroCliente": int(os.environ.get("SICOOB_SANDBOX_NUMERO_CLIENTE", "25546454")),
            "codigoModalidade": 1,
            "chave_pix": os.environ.get("SICOOB_SANDBOX_CHAVE_PIX") or "sandbox@sicoob.com.br",
        },
        credentials={
            "client_id": os.environ["SICOOB_SANDBOX_CLIENT_ID"],
            "access_token": os.environ["SICOOB_SANDBOX_TOKEN"],  # estático, sem OAuth
        },
    )


def test_sandbox_consultar_boleto_e_segunda_via(provider):
    # O mock do sandbox devolve 400 enlatado no POST de emissão (limitação
    # conhecida do simulador); a CONSULTA devolve o contrato completo — é o que
    # valida o mapeamento do provider.
    out = provider.consultar("123")
    assert out.linha_digitavel, out.raw
    assert (out.raw.get("resultado") or {}).get("codigoBarras")

    pdf = provider.pdf("123")  # rota /boletos/segunda-via (200 no sandbox)
    assert pdf.raw


def test_sandbox_emitir_boleto_mock_enlatado(provider):
    """Emissão no mock: 400 enlatado ("string") — documenta a limitação.
    O contrato do payload é validado pela consulta acima e nos testes de mock."""
    import httpx
    from datetime import date, timedelta

    from app.schemas import Cobranca, Pagador

    try:
        out = provider.registrar(Cobranca(
            valor="10.00", vencimento=date.today() + timedelta(days=30),
            seu_numero=uuid.uuid4().hex[:10],
            pagador=Pagador(nome="Teste", documento="12345678909",
                            endereco={"endereco": "Av. Teste, 100", "bairro": "Centro",
                                      "cidade": "BH", "uf": "MG", "cep": "30000000"}),
        ))
        assert out.id  # se o mock aceitar, melhor ainda
    except httpx.HTTPStatusError as e:
        assert e.response.status_code == 400  # resposta enlatada do simulador


def test_sandbox_pix_cob_imediata(provider):
    from app.schemas import PixCobranca

    assert provider.account_config.get("chave_pix")
    out = provider.criar_pix(PixCobranca(valor="1.00", descricao="teste sandbox sicoob"))
    assert out.pix_copia_cola or out.txid, out.raw  # Sicoob devolve brcode


def test_sandbox_pix_recebidos(provider):
    from datetime import datetime, timedelta, timezone

    hoje = datetime.now(timezone.utc)
    data = provider.listar_pix_recebidos(
        inicio=(hoje - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z"),
        fim=hoje.strftime("%Y-%m-%dT23:59:59Z"),
    )
    assert isinstance(data, dict), data  # 200 com lista (pode vir vazia)


def test_sandbox_pix_automatico_criar_recorrencia(provider):
    """PA no Sicoob: mesmo dialeto BACEN — POST /pix/api/v2/rec (200 no sandbox)."""
    data = provider.criar_recorrencia({
        "vinculo": {"contrato": "CT-SANDBOX-1", "objeto": "Homologacao PA",
                    "devedor": {"nome": "Jose Teste", "cpf": "12345678909"}},
        "calendario": {"dataInicial": "2026-08-01", "periodicidade": "MENSAL"},
        "valor": {"valorRec": "50.00"},
        "politicaRetentativa": "NAO_PERMITE",
    })
    assert isinstance(data, dict), data
