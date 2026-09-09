#!/usr/bin/env python3
"""Smoke-test the Lambda container through the bundled Runtime Interface
Emulator (RIE). The image is started with `docker run -p 9000:8080 <image>`,
which runs the RIE on :8080 and the actual handler through the RIC.

Usage:
    python3 test/lambda_rie_smoke.py [base_url]

Only the standard library is used so it runs on a bare GitHub Actions runner.
"""
import base64
import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else (
    "http://localhost:9000/2015-03-31/functions/function/invocations"
)

FAILURES = 0


def invoke(event):
    req = urllib.request.Request(
        BASE,
        data=json.dumps(event).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def check(desc, ok):
    global FAILURES
    print(("PASS" if ok else "FAIL") + ": " + desc)
    if not ok:
        FAILURES += 1


def multipart_event(path, fields, files):
    boundary = "----BoletoCnabApiRie"
    body = b""
    for name, value in fields:
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
    for name, filename, content in files:
        body += (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; "
            f"filename=\"{filename}\"\r\nContent-Type: application/octet-stream\r\n\r\n"
        ).encode()
        body += content + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return {
        "httpMethod": "POST",
        "path": path,
        "headers": {"content-type": f"multipart/form-data; boundary={boundary}"},
        "body": base64.b64encode(body).decode(),
        "isBase64Encoded": True,
    }


BOLETO = {
    "valor": 5.0,
    "cedente": "Kivanio Barbosa",
    "documento_cedente": "12345678912",
    "sacado": "Claudio Pozzebom",
    "sacado_documento": "12345678900",
    "agencia": "0810",
    "conta_corrente": "53678",
    "convenio": 12387,
    "nosso_numero": "12345678",
    "data_vencimento": "2026/12/31",
}

# 1. JSON endpoint
resp = invoke({
    "httpMethod": "GET",
    "path": "/api/boleto/validate",
    "queryStringParameters": {"bank": "itau", "data": json.dumps(BOLETO)},
    "headers": {},
    "isBase64Encoded": False,
})
check("validate returns 200 and true", resp["statusCode"] == 200 and resp["body"] == "true")

# 2. binary endpoint (PDF)
resp = invoke({
    "httpMethod": "GET",
    "path": "/api/boleto",
    "queryStringParameters": {"bank": "itau", "type": "pdf", "data": json.dumps(BOLETO)},
    "headers": {},
    "isBase64Encoded": False,
})
pdf_ok = (
    resp["statusCode"] == 200
    and resp.get("isBase64Encoded") is True
    and base64.b64decode(resp["body"]).startswith(b"%PDF")
)
check("boleto PDF returned base64 with %PDF magic", pdf_ok)

# 3. multipart file endpoint (remessa)
remessa = {
    "carteira": "123",
    "agencia": "1234",
    "conta_corrente": "12345",
    "digito_conta": "1",
    "empresa_mae": "SOCIEDADE BRASILEIRA GNU LTDA",
    "documento_cedente": "12345678910",
    "pagamentos": [{
        "valor": 199.9,
        "data_vencimento": "2026/06/15",
        "nosso_numero": 123,
        "documento": 6969,
        "documento_sacado": "12345678901",
        "nome_sacado": "PABLO",
        "endereco_sacado": "RUA",
        "bairro_sacado": "B",
        "cep_sacado": "12345678",
        "cidade_sacado": "C",
        "uf_sacado": "SP",
    }],
}
resp = invoke(multipart_event(
    "/api/remessa",
    [("bank", "itau"), ("type", "cnab400")],
    [("data", "remessa_data.json", json.dumps(remessa).encode())],
))
rem_ok = (
    resp["statusCode"] == 201
    and base64.b64decode(resp["body"]).startswith(b"01REMESSA")
)
check("remessa cnab400 returned base64 with 01REMESSA header", rem_ok)

print()
if FAILURES == 0:
    print("ALL RIE SMOKE CHECKS PASSED")
else:
    print(f"{FAILURES} CHECK(S) FAILED")
    sys.exit(1)
