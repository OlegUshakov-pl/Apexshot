from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LANGUAGES: dict[str, str] = {
    "en": "English",
    "pl": "Polski",
    "ru": "Русский",
}
DEFAULT_LANG = "en"

LOCALES_DIR = Path(__file__).resolve().parent / "locales"

_lang: str = DEFAULT_LANG
_cache: dict[str, dict[str, str]] = {}


def set_language(lang: str | None) -> None:
    global _lang
    _lang = lang if lang in LANGUAGES else DEFAULT_LANG


def get_language() -> str:
    return _lang


def _load(lang: str) -> dict[str, str]:
    cached = _cache.get(lang)
    if cached is not None:
        return cached
    merged: dict[str, str] = {}
    folder = LOCALES_DIR / lang
    if folder.is_dir():
        for path in sorted(folder.glob("*.json")):
            try:
                data: Any = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                merged.update({str(k): str(v) for k, v in data.items()})
    _cache[lang] = merged
    return merged


def reload() -> None:
    _cache.clear()


def t(key: str, **kwargs: Any) -> str:
    """Translate `key` (source language is Russian) into the current language."""
    lang = get_language()
    text = _load(lang).get(key)
    if text is None and lang != "ru":
        text = _load(DEFAULT_LANG).get(key)
    if text is None:
        text = key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text


def as_dict(lang: str | None = None) -> dict[str, str]:
    """Flat translation map for the given language (used by the JS helper)."""
    target = lang or get_language()
    if target == "ru":
        return {}
    return dict(_load(target))
