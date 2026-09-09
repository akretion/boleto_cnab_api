import json
import tempfile
from pathlib import Path

import requests
import subprocess
import time


def test_run():
    cmd = ["docker", "build", "-t", "akretion/boleto_cnab_api", "."]
    result = subprocess.run(
        cmd, check=False, capture_output=True, text=True, cwd=Path(__file__).parent.parent
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
    try:
        # The curl smoke tests reproduce the data and expected values from the
        # upstream BRCobranca RSpec suite, see test/curl_tests.sh.
        cmd = ["bash", str(Path(__file__).parent / "curl_tests.sh")]
        result = subprocess.run(
            cmd, check=False, capture_output=True, text=True, timeout=300
        )
        # always echo the curl suite output, pass or fail
        print("\n" + result.stdout)
        if result.stderr:
            print(result.stderr)
        assert result.returncode == 0, (
            "curl smoke tests failed:\n" + result.stdout + "\n" + result.stderr
        )

        # The committed docs/openapi.json must match the live API definition
        # (regenerate with: bundle exec ruby scripts/generate_openapi.rb)
        cmd = [
            "docker", "exec", "-u", "root", "boleto_cnab_api",
            "bundle", "exec", "ruby", "scripts/generate_openapi.rb",
        ]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr + "\n" + result.stdout
        cmd = [
            "docker", "cp",
            "boleto_cnab_api:/usr/src/app/docs/openapi.json",
            "/tmp/openapi_live.json",
        ]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr + "\n" + result.stdout
        committed = Path(__file__).parent.parent / "docs" / "openapi.json"
        assert committed.read_text() == Path("/tmp/openapi_live.json").read_text(), (
            "docs/openapi.json is stale; regenerate it with "
            "'bundle exec ruby scripts/generate_openapi.rb'"
        )

        # Optional API key auth (API_KEYS env var): a protected instance must
        # reject anonymous/wrong-key requests with 401 and accept the
        # AWS-API-Gateway-compatible X-Api-Key header or HTTP Basic auth
        # (password = key). See lib/api_key_auth.rb.
        cmd = ["docker", "rm", "-f", "boleto_cnab_api"]
        subprocess.run(cmd, check=False, capture_output=True, text=True)
        cmd = [
            "docker", "run", "-d", "-p", "9292:9292",
            "-e", "API_KEYS=test-key-1,test-key-2",
            "--name=boleto_cnab_api", "akretion/boleto_cnab_api",
        ]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr + "\n" + result.stdout
        time.sleep(5)

        base = "http://localhost:9292"
        params = {
            "bank": "itau",
            "data": '{"valor":5.0,"cedente":"Kivanio Barbosa",'
                    '"documento_cedente":"12345678912","sacado":"Claudio Pozzebom",'
                    '"sacado_documento":"12345678900","agencia":"0810",'
                    '"conta_corrente":"53678","convenio":12387,'
                    '"nosso_numero":"12345678","data_vencimento":"2026/12/31"}',
        }

        response = requests.get(f"{base}/api/boleto/validate", params=params)
        assert response.status_code == 401, response.status_code

        response = requests.get(
            f"{base}/api/boleto/validate",
            params=params,
            headers={"X-Api-Key": "wrong-key"},
        )
        assert response.status_code == 401, response.status_code

        response = requests.get(
            f"{base}/api/boleto/validate",
            params=params,
            headers={"X-Api-Key": "test-key-1"},
        )
        assert response.status_code == 200 and response.json() is True, (
            response.status_code
        )

        response = requests.get(
            f"{base}/api/boleto/validate", params=params, auth=("odoo", "test-key-2")
        )
        assert response.status_code == 200 and response.json() is True, (
            response.status_code
        )

        response = requests.get(f"{base}/docs")
        assert response.status_code == 401, response.status_code
    finally:
        cmd = ["docker", "logs", "boleto_cnab_api"]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        print("\n--- boleto_cnab_api container logs ---")
        print(result.stdout)
        print(result.stderr)
        cmd = ["docker", "rm", "-f", "boleto_cnab_api"]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr + "\n" + result.stdout
