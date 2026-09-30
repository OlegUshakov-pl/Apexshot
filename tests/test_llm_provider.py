from __future__ import annotations

import pytest

from app.schemas import SettingsOut
from app.services import llm_provider


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
