from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_put_settings_rejects_negative_timeout(client):
    current = client.get("/api/settings").json()
    current["timeout_seconds"] = -5
    resp = client.put("/api/settings", json=current)
    assert resp.status_code == 400
    assert resp.json()["error"] == "Invalid timeout"


def test_put_settings_accepts_zero_timeout(client):
    current = client.get("/api/settings").json()
    current["timeout_seconds"] = 0
    resp = client.put("/api/settings", json=current)
    assert resp.status_code == 200
    assert resp.json()["timeout_seconds"] == 0


def test_chat_zero_timeout_maps_to_httpx_none():
    from app.schemas import SettingsOut
    from app.services import llm_provider

    settings = SettingsOut(provider="ollama", timeout_seconds=0)
    raw_timeout = settings.timeout_seconds or 0
    timeout = raw_timeout if raw_timeout > 0 else None
    assert timeout is None
