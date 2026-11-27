"""
Tests for the pass(1) integration in auth, with pass itself replaced by fakes
so nothing touches a real password store or the network.
"""

import json
from typing import Any
from unittest.mock import Mock

import pytest
from google.oauth2.credentials import Credentials

from pygooglehelper import auth
from pygooglehelper.configs import ConfigAuth, ConfigRequest

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CLIENT = {"installed": {"client_id": "id", "client_secret": "s", "token_uri": "https://oauth2.googleapis.com/token"}}


def _token_info(scopes: list[str]) -> dict[str, Any]:
    return {
        "client_id": "id",
        "client_secret": "s",
        "refresh_token": "r1",
        "scopes": scopes,
        "token_uri": "https://oauth2.googleapis.com/token",
    }


class FakePass:
    """ an in-memory pass store """

    def __init__(self, entries: dict[str, str]) -> None:
        self.entries = entries
        self.inserts: list[str] = []

    def show(self, entry: str) -> str | None:
        return self.entries.get(entry)

    def insert(self, entry: str, content: str) -> bool:
        self.entries[entry] = content
        self.inserts.append(entry)
        return True


@pytest.fixture(name="store")
def fixture_store(monkeypatch: pytest.MonkeyPatch) -> FakePass:
    fake = FakePass({})
    monkeypatch.setattr(auth, "_pass_show", fake.show)
    monkeypatch.setattr(auth, "_pass_insert", fake.insert)
    monkeypatch.setattr(ConfigRequest, "scopes", SCOPES)
    monkeypatch.setattr(ConfigRequest, "gcp_project", "proj")
    monkeypatch.setattr(ConfigAuth, "force", False)
    return fake


def test_client_config_from_pass(store: FakePass) -> None:
    assert auth.get_pass_client_config() is None
    store.entries["gcp/proj/oauth-client"] = json.dumps(CLIENT)
    assert auth.get_pass_client_config() == CLIENT


def test_no_project_means_no_pass(store: FakePass, monkeypatch: pytest.MonkeyPatch) -> None:
    store.entries["gcp/proj/oauth-client"] = json.dumps(CLIENT)
    monkeypatch.setattr(ConfigRequest, "gcp_project", None)
    assert auth.get_pass_client_config() is None


def test_bad_client_entry_is_ignored(store: FakePass) -> None:
    store.entries["gcp/proj/oauth-client"] = "not json"
    assert auth.get_pass_client_config() is None
    store.entries["gcp/proj/oauth-client"] = json.dumps({"other": 1})
    assert auth.get_pass_client_config() is None


def test_refresh_does_not_write_pass(store: FakePass, monkeypatch: pytest.MonkeyPatch) -> None:
    store.entries["gcp/proj/token"] = json.dumps(_token_info(SCOPES))

    def fake_refresh(self: Credentials, _request: object) -> None:
        self.token = "access"

    monkeypatch.setattr(Credentials, "refresh", fake_refresh)
    credentials = auth.get_credentials()
    assert credentials.token == "access"
    assert not store.inserts


def test_changed_refresh_token_is_written_without_access_token(store: FakePass, monkeypatch: pytest.MonkeyPatch) -> None:
    store.entries["gcp/proj/token"] = json.dumps(_token_info(SCOPES))

    def fake_refresh(self: Credentials, _request: object) -> None:
        self.token = "access"
        self._refresh_token = "r2"

    monkeypatch.setattr(Credentials, "refresh", fake_refresh)
    auth.get_credentials()
    assert store.inserts == ["gcp/proj/token"]
    saved = json.loads(store.entries["gcp/proj/token"])
    assert saved["refresh_token"] == "r2"
    assert "token" not in saved
    assert "expiry" not in saved


def test_missing_token_authorizes_and_stores_in_pass(store: FakePass, monkeypatch: pytest.MonkeyPatch) -> None:
    store.entries["gcp/proj/oauth-client"] = json.dumps(CLIENT)
    fresh = Credentials(
        token="access", refresh_token="r9", client_id="id", client_secret="s",
        token_uri="https://oauth2.googleapis.com/token", scopes=SCOPES,
    )
    def authorize(client_config: dict[str, Any]) -> Credentials | None:
        return fresh if client_config == CLIENT else None

    monkeypatch.setattr(auth, "_authorize", authorize)
    assert auth.get_credentials() is fresh
    saved = json.loads(store.entries["gcp/proj/token"])
    assert saved["refresh_token"] == "r9"
    assert "token" not in saved


def test_scopes_not_covered_reauthorizes(store: FakePass, monkeypatch: pytest.MonkeyPatch) -> None:
    store.entries["gcp/proj/oauth-client"] = json.dumps(CLIENT)
    store.entries["gcp/proj/token"] = json.dumps(_token_info(["https://www.googleapis.com/auth/other"]))
    fresh = Credentials(
        token="access", refresh_token="r9", client_id="id", client_secret="s",
        token_uri="https://oauth2.googleapis.com/token", scopes=SCOPES,
    )
    monkeypatch.setattr(auth, "_authorize", Mock(return_value=fresh))
    assert auth.get_credentials() is fresh
    assert store.inserts == ["gcp/proj/token"]
