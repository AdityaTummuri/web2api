"""Shared pytest setup: isolate tests from any real api.txt / env keys on this machine."""

import os

import pytest


@pytest.fixture(autouse=True)
def _isolated_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB2API_KEYS_FILE", str(tmp_path / "no-keys.txt"))
    for var in ("WEB2API_API_KEY", "API_KEY", "WEB2API_REQUIRE_AUTH", "WEB2API_ALLOW_INSECURE"):
        monkeypatch.delenv(var, raising=False)
    yield
    os.environ.pop("WEB2API_KEYS_FILE", None)
