# E2E contra o SANDBOX real do C6 — roda só com credenciais no ambiente.
#
# Requisitos (nunca commitar valores):
#   C6_SANDBOX_CLIENT_ID / C6_SANDBOX_CLIENT_SECRET  (e-mail de onboarding C6)
#   C6_SANDBOX_PFX_BASE64 / C6_SANDBOX_PFX_PASSWORD  (certificado mTLS do portal)
#   C6_SANDBOX_CHAVE_PIX                             (chave Pix do sandbox)
# Janela do sandbox: seg-sex, 7h-23h (BRT). Fora disso o banco não responde.
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    not (os.environ.get("C6_SANDBOX_CLIENT_ID") and os.environ.get("C6_SANDBOX_CLIENT_SECRET")),
    reason="sem credenciais C6_SANDBOX_* no ambiente",
)


@pytest.fixture
def provider():
    from app.providers.c6 import C6Provider

    return C6Provider(
        account_config={"chave_pix": os.environ.get("C6_SANDBOX_CHAVE_PIX", "")},
        credentials={
            "client_id": os.environ["C6_SANDBOX_CLIENT_ID"],
            "client_secret": os.environ["C6_SANDBOX_CLIENT_SECRET"],
            "pfx_base64": os.environ.get("C6_SANDBOX_PFX_BASE64", ""),
            "pfx_password": os.environ.get("C6_SANDBOX_PFX_PASSWORD", ""),
        },
    )


def test_sandbox_emitir_consultar_cancelar_boleto(provider):
    import time
    from datetime import date, timedelta

    import httpx

    from app.schemas import Cobranca, Pagador, Status

    ref = uuid.uuid4().hex[:10]  # external_reference_id: alfanum 1-10
    out = provider.registrar(Cobranca(
        valor="10.00",
        vencimento=date.today() + timedelta(days=30),
        seu_numero=ref,
        pagador=Pagador(
            nome="Teste Sandbox",
            documento="12345678909",
            endereco={"street": "Av. Teste", "number": 1, "city": "Sao Paulo",
                      "state": "SP", "zip_code": "01000000"},
        ),
    ))
    assert out.id, out.raw
    assert out.linha_digitavel

    consultado = provider.consultar(out.id)
    assert consultado.status in (Status.registrado, Status.pendente)

    # O registro no banco é assíncrono: cancelar logo após emitir responde 400
    # ("já existe uma requisição em processamento"). Aguarda e re-tenta — o
    # tempo de processamento do sandbox varia (observado de ~10s a minutos).
    ultimo_erro = ""
    for _ in range(18):
        try:
            baixado = provider.baixar(out.id)
            break
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 400:
                raise
            ultimo_erro = e.response.text[:200]
            time.sleep(10)
    else:
        raise AssertionError(f"cancelamento não processado em 180s: {ultimo_erro}")
    assert baixado.status == Status.baixado
    assert provider.consultar(out.id).status == Status.baixado  # CANCELLED no banco


def test_sandbox_pix_cob_imediata(provider):
    from app.schemas import PixCobranca

    if not provider.account_config.get("chave_pix"):
        pytest.skip("sem C6_SANDBOX_CHAVE_PIX")
    out = provider.criar_pix(PixCobranca(valor="1.00", descricao="teste sandbox"))
    assert out.txid, out.raw
    assert out.pix_copia_cola or out.location
