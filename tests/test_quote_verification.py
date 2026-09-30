from __future__ import annotations

import pytest

from app.services.snapshot_generator import verify_quotes

CORPUS = (
    "### Файл: readme.md\n"
    "Ollama — популярный способ запускать локальные LLM прямо на компьютере. "
    "Локальные LLM помогают сохранить приватность данных.\n"
)


def test_exact_quote_verified():
    data = {
        "facts": [
            {
                "id": "f1",
                "claim": "Ollama запускает LLM",
                "quote": "Ollama — популярный способ запускать локальные LLM прямо на компьютере",
                "confidence": 0.9,
                "type": "verified",
            }
        ],
        "highlights": [],
    }
    fact = verify_quotes(data, CORPUS)["facts"][0]
    assert fact["verified"] is True
    assert fact["confidence"] == pytest.approx(0.9)
    assert fact["quality"] == "ok"


def test_normalized_whitespace_verified():
    quote = "Ollama — популярный   способ запускать\nлокальные LLM"
    data = {"facts": [{"id": "f1", "claim": "c", "quote": quote, "confidence": 0.8}], "highlights": []}
    assert verify_quotes(data, CORPUS)["facts"][0]["verified"] is True


def test_quote_not_found_lowers_confidence():
    data = {
        "facts": [{"id": "f1", "claim": "c", "quote": "Совершенно другая фраза", "confidence": 0.9}],
        "highlights": [],
    }
    fact = verify_quotes(data, CORPUS)["facts"][0]
    assert fact["verified"] is False
    assert fact["confidence"] == pytest.approx(0.7)
    assert fact["quality"] == "ok"


def test_low_quality_marking():
    data = {
        "facts": [{"id": "f1", "claim": "c", "quote": "нет такого", "confidence": 0.4}],
        "highlights": [],
    }
    fact = verify_quotes(data, CORPUS)["facts"][0]
    assert fact["verified"] is False
    assert fact["confidence"] == pytest.approx(0.2)
    assert fact["quality"] == "low_quality"


def test_partial_match_counts_as_missing():
    data = {
        "facts": [
            {"id": "f1", "claim": "c", "quote": "популярный способ запускать в браузере", "confidence": 0.7}
        ],
        "highlights": [],
    }
    assert verify_quotes(data, CORPUS)["facts"][0]["verified"] is False


def test_multiple_facts_and_highlights():
    data = {
        "facts": [
            {"id": "f1", "claim": "a", "quote": "Локальные LLM помогают сохранить приватность данных", "confidence": 0.9},
            {"id": "f2", "claim": "b", "quote": "выдуманная цитата", "confidence": 0.9},
        ],
        "highlights": [
            {"quote": "Локальные LLM помогают сохранить приватность данных"},
            {"quote": "ничего подобного в тексте"},
        ],
    }
    out = verify_quotes(data, CORPUS)
    assert out["facts"][0]["verified"] is True
    assert out["facts"][1]["verified"] is False
    assert out["facts"][1]["confidence"] == pytest.approx(0.7)
    assert out["highlights"][0]["verified"] is True
    assert out["highlights"][1]["verified"] is False
