"""Security tests: per-install keys, enforced auth, WebSocket token, safe bind defaults."""

import os
import stat
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import bridge_server
import web2api_keys
from bridge_server import app, check_startup_security, is_loopback_host

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAT = {"model": "gemini-pro", "messages": [{"role": "user", "content": "hi"}]}


@pytest.fixture
def keyed(tmp_path, monkeypatch):
    path = tmp_path / "api.txt"
    web2api_keys.generate_keys_file(str(path))
    monkeypatch.setenv("WEB2API_KEYS_FILE", str(path))
    return web2api_keys.load_keys()


def test_generated_keys_are_random_private_and_loadable(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    web2api_keys.generate_keys_file(str(a))
    web2api_keys.generate_keys_file(str(b))
    assert stat.S_IMODE(os.stat(a).st_mode) == 0o600
    assert set(web2api_keys.KEY_PATTERN.findall(a.read_text())).isdisjoint(
        web2api_keys.KEY_PATTERN.findall(b.read_text())
    )


def test_generate_refuses_to_overwrite(tmp_path):
    path = tmp_path / "api.txt"
    web2api_keys.generate_keys_file(str(path))
    with pytest.raises(FileExistsError):
        web2api_keys.generate_keys_file(str(path))


def test_previously_committed_keys_are_rejected(tmp_path, monkeypatch):
    path = tmp_path / "api.txt"
    path.write_text("KEY: sk-w2a-dev-a7d4e1f9b3c820564917a2e8df3c9041\n")
    monkeypatch.setenv("WEB2API_KEYS_FILE", str(path))
    assert web2api_keys.load_keys() == []
    assert web2api_keys._has_only_revoked_keys(str(path))


def test_requests_without_key_are_rejected_once_keys_exist(keyed):
    client = TestClient(app)
    assert client.post("/v1/chat/completions", json=CHAT).status_code == 401
    bad = {"Authorization": "Bearer sk-w2a-dev-wrongwrongwrongwrong"}
    assert client.post("/v1/chat/completions", json=CHAT, headers=bad).status_code == 401


def test_valid_key_passes_auth(keyed):
    client = TestClient(app)
    for headers in ({"Authorization": f"Bearer {keyed[0]}"}, {"X-API-Key": keyed[1]}):
        # Anything but 401 means auth passed (503 if no extension is connected, 200 with a mock one)
        assert client.post("/v1/chat/completions", json=CHAT, headers=headers).status_code != 401


def test_health_reports_auth_required(keyed):
    assert TestClient(app).get("/health").json()["auth_required"] is True


def test_websocket_requires_token_when_keys_exist(keyed):
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()
    with client.websocket_connect(f"/ws?token={keyed[0]}") as ws:
        ws.send_text('{"type": "HANDSHAKE", "client": "test"}')
    bridge_server.hub.disconnect()


def test_default_bind_is_loopback():
    env = {k: v for k, v in os.environ.items() if k != "HOST"}
    out = subprocess.run(
        [sys.executable, "-c", "import bridge_server; print(bridge_server.HOST)"],
        cwd=ROOT, env=env, capture_output=True, text=True, check=True,
    )
    assert out.stdout.strip() == "127.0.0.1"


@pytest.mark.parametrize("host,expected", [("127.0.0.1", True), ("localhost", True), ("::1", True),
                                           ("0.0.0.0", False), ("100.101.102.103", False), ("", False)])
def test_is_loopback_host(host, expected):
    assert is_loopback_host(host) is expected


def test_refuses_network_bind_without_keys():
    assert check_startup_security("0.0.0.0") is not None
    assert check_startup_security("127.0.0.1") is None


def test_allows_network_bind_with_keys(keyed):
    assert check_startup_security("0.0.0.0") is None


def test_insecure_override(monkeypatch):
    monkeypatch.setenv("WEB2API_ALLOW_INSECURE", "1")
    assert check_startup_security("0.0.0.0") is None


def test_parse_hosts():
    from bridge_server import parse_hosts

    assert parse_hosts("127.0.0.1, 100.64.1.2") == ["127.0.0.1", "100.64.1.2"]
    assert parse_hosts("") == ["127.0.0.1"]


def test_multi_host_refuses_without_keys():
    from bridge_server import parse_hosts

    assert [h for h in parse_hosts("127.0.0.1,100.64.1.2") if check_startup_security(h)] == ["100.64.1.2"]


def test_tokens_are_redacted_from_logs():
    import logging

    from bridge_server import RedactTokensFilter

    rec = logging.LogRecord("uvicorn.error", logging.INFO, __file__, 1,
                            '%s - "WebSocket %s" [accepted]', ("127.0.0.1:1", "/ws?token=sk-w2a-dev-secret123456789"), None)
    RedactTokensFilter().filter(rec)
    assert "secret" not in rec.getMessage()
    assert "token=***" in rec.getMessage()
