import json
import tempfile
from pathlib import Path
import os
import subprocess
import requests
import time


def test_run():
    cmd = ["docker", "build", "-t", "akretion/boleto_cnab_api", "."]
    result = subprocess.run(
        cmd, check=False, capture_output=True, text=True, cwd=Path(__file__).parent
    )
    assert result.returncode == 0, result.stderr + "\n" + result.stdout

    cmd = [
        "docker",
        "run",
        "-d",
        "-p",
        "9292:9292",
        "--name=boleto_cnab_api",
        "akretion/boleto_cnab_api",
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + "\n" + result.stdout
    time.sleep(5)
    remessa_values = [
        {
            "valor": 5.0,
            "cedente": "Kivanio Barbosa",
            "documento_cedente": "12345678912",
            "sacado": "Claudio Pozzebom",
            "sacado_documento": "12345678900",
            "agencia": "0810",
            "conta_corrente": "53678",
            "convenio": 12387,
            "nosso_numero": "12345678",
            "bank": "itau",
        },
        {
            "valor": 10.00,
            "cedente": "PREFEITURA MUNICIPAL DE VILHENA",
            "documento_cedente": "04092706000181",
            "sacado": "João Paulo Barbosa",
            "sacado_documento": "77777777777",
            "agencia": "1825",
            "conta_corrente": "0000528",
            "convenio": "245274",
            "nosso_numero": "000000000000001",
            "bank": "caixa",
        },
    ]
    content = json.dumps(remessa_values)
    with open(tempfile.mktemp(), "w") as f:
        file_name = f.name
        f.write(content)
    files = {"data": open(file_name, "rb")}
    result = requests.post(
        "http://localhost:9292/api/boleto/multi",
        data={
            "type": "pdf",
        },
        files=files,
    )
    assert str(result.status_code)[0] == "2"

    cmd = ["docker", "rm", "-f", "boleto_cnab_api"]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + "\n" + result.stdout
