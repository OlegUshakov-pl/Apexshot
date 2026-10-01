from __future__ import annotations

import json

import pytest

from app.services import snapshot_generator as sg


VALID_DOC = {
    "title": "T",
    "summary": "S",
    "facts": [{"id": "f1", "claim": "c", "quote": "q", "confidence": 0.9}],
    "confidence": 0.9,
}

SCHEMA_ECHO = json.dumps(
    {
        "type": "object",
        "required": ["title", "summary"],
        "properties": {"title": {"type": "string"}, "summary": {"type": "string"}},
    }
)


def test_valid_doc_passes():
    assert sg.parse_snapshot_response(json.dumps(VALID_DOC))["title"] == "T"


def test_empty_object_rejected():
    with pytest.raises(sg.JsonParseError):
        sg.parse_snapshot_response("{}")


def test_schema_echo_rejected():
    with pytest.raises(sg.JsonParseError):
        sg.parse_snapshot_response(SCHEMA_ECHO)


def test_schema_echo_with_data_is_unwrapped():
    raw = json.dumps(
        {
            "type": "object",
            "properties": {
                "title": "Real title",
                "summary": "Real summary",
                "facts": [{"id": "f1", "claim": "c", "quote": "q"}],
            },
        }
    )
    parsed = sg.parse_snapshot_response(raw)
    assert parsed["title"] == "Real title"


def test_schema_echo_fields_do_not_leak():
    data = sg.unwrap_schema_echo(
        {"type": "object", "properties": {"title": {"type": "string"}}}
    )
    doc = sg.normalize_snapshot_doc(data)
    assert doc["title"] == ""
    assert not sg.has_content(doc)


def test_normalize_ignores_non_string_values():
    doc = sg.normalize_snapshot_doc(
        {
            "title": {"type": "string"},
            "summary": ["x"],
            "questions": {"a": 1},
            "tags": "nope",
            "facts": "nope",
            "confidence": "abc",
        }
    )
    assert doc["title"] == ""
    assert doc["summary"] == ""
    assert doc["questions"] == []
    assert doc["tags"] == []
    assert doc["facts"] == []
    assert doc["confidence"] == 0.0
    assert not sg.has_content(doc)


def test_retry_parses_new_response(monkeypatch):
    responses = [json.dumps(VALID_DOC)]
    calls = []

    def fake_call(system_prompt, user_prompt, settings):
        calls.append(user_prompt)
        return responses.pop(0)

    monkeypatch.setattr(sg, "_call_llm", fake_call)
    out = sg._parse_with_retry("bad", "sys", "user", settings=None)
    assert out["title"] == "T"
    assert len(calls) == 1


def test_schema_echo_triggers_retry(monkeypatch):
    responses = [json.dumps(VALID_DOC)]
    monkeypatch.setattr(sg, "_call_llm", lambda *a, **k: responses.pop(0))
    out = sg._parse_with_retry(SCHEMA_ECHO, "sys", "user", settings=None)
    assert out["title"] == "T"


def test_retry_exhausted_raises(monkeypatch):
    monkeypatch.setattr(sg, "_call_llm", lambda *a, **k: "still not json")
    with pytest.raises(sg.GenerationError):
        sg._parse_with_retry("bad", "sys", "user", settings=None)


def test_retry_keeps_provider_error(monkeypatch):
    from app.services import llm_provider

    def boom(*a, **k):
        raise llm_provider.ProviderError("Provider unreachable", "down")

    monkeypatch.setattr(sg, "_call_llm", boom)
    with pytest.raises(llm_provider.ProviderError):
        sg._parse_with_retry("bad", "sys", "user", settings=None)


def test_verify_quotes_handles_non_string_quote():
    out = sg.verify_quotes({"facts": [{"id": "f1", "quote": {"a": 1}}]}, "text")
    assert out["facts"][0]["quote"] == ""
    assert out["facts"][0]["verified"] is False
