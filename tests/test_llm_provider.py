from __future__ import annotations

import pytest

from app.schemas import SettingsOut
from app.services import llm_provider


@pytest.fixture(autouse=True)
def _clear_fallback_cache():
    llm_provider.clear_model_fallback_cache()
    yield
    llm_provider.clear_model_fallback_cache()


def test_normalize_ollama_default():
    assert llm_provider.normalize_base_url("ollama", "") == "http://localhost:11434"
    assert llm_provider.normalize_base_url("ollama", "http://localhost:11434/") == "http://localhost:11434"


def test_normalize_lmstudio_adds_v1():
    assert llm_provider.normalize_base_url("lmstudio", "http://localhost:1234") == "http://localhost:1234/v1"
    assert llm_provider.normalize_base_url("lmstudio", "http://localhost:1234/v1") == "http://localhost:1234/v1"
    assert llm_provider.normalize_base_url("lmstudio", "http://localhost:1234/v1/") == "http://localhost:1234/v1"


def test_connection_refused_reports_unreachable():
    result = llm_provider.test_connection("ollama", "http://127.0.0.1:1", "", "llama3.1:8b")
    assert result.reachable is False
    assert result.model_available is False
    assert result.error


def test_chat_raises_provider_error_when_unreachable():
    settings = SettingsOut(
        provider="ollama",
        base_url="http://127.0.0.1:1",
        model="llama3.1:8b",
        timeout_seconds=5,
    )
    with pytest.raises(llm_provider.ProviderError) as exc:
        llm_provider.chat("system", "user", settings)
    assert exc.value.message in {"Provider unreachable", "Provider timeout"}


def test_headers_with_and_without_key():
    assert "Authorization" not in llm_provider._headers("")
    assert llm_provider._headers("secret")["Authorization"] == "Bearer secret"


def test_chat_zero_timeout_disables_httpx_timeout(monkeypatch):
    seen: dict = {}

    class FakeResp:
        status_code = 200
        text = "{}"

        def json(self):
            return {"message": {"content": "ok"}}

    class FakeClient:
        def __init__(self, timeout=None, headers=None):
            seen["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None):
            return FakeResp()

    monkeypatch.setattr(llm_provider.httpx, "Client", FakeClient)
    settings = SettingsOut(
        provider="ollama",
        base_url="http://localhost:11434",
        model="m",
        timeout_seconds=0,
    )
    assert llm_provider.chat("system", "user", settings) == "ok"
    assert seen["timeout"] is None


def test_chat_positive_timeout_passed_through(monkeypatch):
    seen: dict = {}

    class FakeResp:
        status_code = 200
        text = "{}"

        def json(self):
            return {"message": {"content": "ok"}}

    class FakeClient:
        def __init__(self, timeout=None, headers=None):
            seen["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None):
            return FakeResp()

    monkeypatch.setattr(llm_provider.httpx, "Client", FakeClient)
    settings = SettingsOut(
        provider="ollama",
        base_url="http://localhost:11434",
        model="m",
        timeout_seconds=300,
    )
    assert llm_provider.chat("system", "user", settings) == "ok"
    assert seen["timeout"] == 300


# ---------------------------------------------------------------- fallback
def test_resolve_returns_exact_when_installed(monkeypatch):
    monkeypatch.setattr(llm_provider, "list_models", lambda *a, **kw: ["gemma4:e4b"])
    assert llm_provider.resolve_local_model("ollama", "http://x", "", "gemma4:e4b") == "gemma4:e4b"


def test_resolve_picks_same_family(monkeypatch):
    monkeypatch.setattr(
        llm_provider, "list_models",
        lambda *a, **kw: ["gemma4:12b", "bge-m3:latest"],
    )
    assert llm_provider.resolve_local_model("ollama", "http://x", "", "gemma4:e4b") == "gemma4:12b"


def test_resolve_picks_any_non_embedding(monkeypatch):
    monkeypatch.setattr(
        llm_provider, "list_models",
        lambda *a, **kw: ["bge-m3:latest", "mimo-v2.6:latest"],
    )
    assert llm_provider.resolve_local_model("ollama", "http://x", "", "llama3:8b") == "mimo-v2.6:latest"


def test_resolve_returns_original_when_nothing_installed(monkeypatch):
    monkeypatch.setattr(llm_provider, "list_models", lambda *a, **kw: [])
    assert llm_provider.resolve_local_model("ollama", "http://x", "", "llama3:8b") == "llama3:8b"


def test_resolve_never_raises_when_unreachable(monkeypatch):
    def boom(*a, **kw):
        raise llm_provider.ProviderError("Provider unreachable", "no connect")

    monkeypatch.setattr(llm_provider, "list_models", boom)
    assert llm_provider.resolve_local_model("ollama", "http://x", "", "llama3:8b") == "llama3:8b"


def test_resolve_skips_cloud_providers(monkeypatch):
    def boom(*a, **kw):
        raise AssertionError("list_models must not be called for cloud providers")

    monkeypatch.setattr(llm_provider, "list_models", boom)
    assert llm_provider.resolve_local_model("anthropic", "http://x", "key", "claude-x") == "claude-x"


def test_resolve_uses_cache_within_ttl(monkeypatch):
    calls = []

    def fake_list(*a, **kw):
        calls.append(1)
        return ["m:12b"]

    monkeypatch.setattr(llm_provider, "list_models", fake_list)
    first = llm_provider.resolve_local_model("ollama", "http://x", "", "m:8b")
    second = llm_provider.resolve_local_model("ollama", "http://x", "", "m:8b")
    assert first == second == "m:12b"
    assert len(calls) == 1


def test_chat_uses_resolved_model(monkeypatch):
    seen: dict = {}

    class FakeResp:
        status_code = 200
        text = "{}"

        def json(self):
            return {"message": {"content": "ok"}}

    class FakeClient:
        def __init__(self, timeout=None, headers=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None):
            seen["payload"] = json
            return FakeResp()

    monkeypatch.setattr(llm_provider.httpx, "Client", FakeClient)
    monkeypatch.setattr(llm_provider, "list_models", lambda *a, **kw: ["gemma4:12b"])
    settings = SettingsOut(
        provider="ollama",
        base_url="http://localhost:11434",
        model="gemma4:e4b",
        timeout_seconds=5,
    )
    assert llm_provider.chat("system", "user", settings) == "ok"
    assert seen["payload"]["model"] == "gemma4:12b"
