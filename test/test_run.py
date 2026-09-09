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
    finally:
        cmd = ["docker", "logs", "boleto_cnab_api"]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        print("\n--- boleto_cnab_api container logs ---")
        print(result.stdout)
        print(result.stderr)
        cmd = ["docker", "rm", "-f", "boleto_cnab_api"]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr + "\n" + result.stdout
