from __future__ import annotations

import json

import pytest

from app.services.snapshot_generator import JsonParseError, parse_json_response


VALID = {"title": "t", "summary": "s", "confidence": 0.5}


def test_valid_json():
    assert parse_json_response(json.dumps(VALID)) == VALID


def test_json_in_markdown_fence():
    raw = "```json\n" + json.dumps(VALID) + "\n```"
    assert parse_json_response(raw) == VALID


def test_json_with_extra_text():
    raw = "Вот ответ:\n" + json.dumps(VALID) + "\nНадеюсь помог!"
    assert parse_json_response(raw) == VALID


def test_json_with_trailing_comma():
    raw = '{"title": "t", "confidence": 0.5,}'
    data = parse_json_response(raw)
    assert data["title"] == "t"


def test_invalid_json_raises():
    with pytest.raises(JsonParseError):
        parse_json_response("это не json вовсе")


def test_empty_response_raises():
    with pytest.raises(JsonParseError):
        parse_json_response("")
    with pytest.raises(JsonParseError):
        parse_json_response("   ")
