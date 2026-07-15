import pytest

from app.core.vault import EnvVault


def test_env_vault_reads_credentials(monkeypatch):
    monkeypatch.setenv("VAULT__empresa1__c6__client_id", "cid")
    monkeypatch.setenv("VAULT__empresa1__c6__client_secret", "sec")
    monkeypatch.setenv("VAULT__empresa1__c6__pfx_password", "pw")

    creds = EnvVault().get_credentials("empresa1", "c6")
    assert creds == {"client_id": "cid", "client_secret": "sec", "pfx_password": "pw"}


def test_env_vault_isolates_tenants(monkeypatch):
    monkeypatch.setenv("VAULT__empresa1__c6__client_id", "cid1")
    monkeypatch.setenv("VAULT__empresa2__c6__client_id", "cid2")
    assert EnvVault().get_credentials("empresa2", "c6") == {"client_id": "cid2"}


def test_env_vault_missing_raises(monkeypatch):
    with pytest.raises(KeyError):
        EnvVault().get_credentials("inexistente", "c6")
