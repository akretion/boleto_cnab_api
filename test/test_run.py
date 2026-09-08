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
        print(result.stdout)
        assert result.returncode == 0, (
            "curl smoke tests failed:\n" + result.stdout + "\n" + result.stderr
        )
    finally:
        cmd = ["docker", "rm", "-f", "boleto_cnab_api"]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr + "\n" + result.stdout
