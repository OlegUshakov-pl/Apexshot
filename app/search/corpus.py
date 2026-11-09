"""Общий источник документов для индексов: локальные JSON-слепки.

Один файл из config.SNAPSHOTS_DIR = один слепок. Схема файла поддерживает
как «реальную» (facts — список объектов {claim, quote}, entities — словарь),
так и упрощённую (facts/entities — списки строк) из task.md.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from .. import config

logger = logging.getLogger("search.corpus")

_FIELDS = ("title", "summary", "facts", "entities")


def _fact_text(fact: Any) -> str:
    if isinstance(fact, str):
        return fact
    if isinstance(fact, dict):
        return " ".join(
            str(fact.get(key, "") or "") for key in ("claim", "quote", "text")
        ).strip()
    return str(fact)


def _entity_texts(entities: Any) -> list[str]:
    if isinstance(entities, dict):
        values: list[str] = []
        for value in entities.values():
            if isinstance(value, list):
                values.extend(str(v) for v in value if v)
            elif value:
                values.append(str(value))
        return values
    if isinstance(entities, list):
        return [str(v) for v in entities if v]
    if isinstance(entities, str):
        return [entities] if entities else []
    return []


def fact_texts(doc: dict[str, Any]) -> list[str]:
    return [_fact_text(f) for f in doc.get("facts") or [] if _fact_text(f)]


def entity_list(doc: dict[str, Any]) -> list[str]:
    return _entity_texts(doc.get("entities")) + [str(t) for t in doc.get("tags") or []]


def document_text(doc: dict[str, Any]) -> str:
    """Текст, по которому строится индекс (для ChromaDB и BM25)."""
    parts = [
        str(doc.get("title") or ""),
        str(doc.get("summary") or ""),
        " ".join(fact_texts(doc)),
    ]
    return "\n".join(p for p in parts if p)


def field_texts(doc: dict[str, Any]) -> dict[str, str]:
    """Раздельные тексты полей для matched_fields и snippet.

    facts/entities склеиваются через " | " — на этих границах сниппет
    умеет выделять конкретный факт.
    """
    return {
        "title": str(doc.get("title") or ""),
        "summary": str(doc.get("summary") or ""),
        "facts": " | ".join(fact_texts(doc)),
        "entities": " | ".join(entity_list(doc)),
    }


def captured_at(doc: dict[str, Any]) -> str:
    for key in ("captured_at", "fetched_at"):
        value = doc.get(key)
        if value:
            return str(value)
    return ""


def metadata(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_url": str(doc.get("source_url") or ""),
        "captured_at": captured_at(doc),
        "model_name": str(doc.get("model_name") or doc.get("model") or ""),
        "model_version": str(doc.get("model_version") or doc.get("provider") or ""),
        "schema_version": int(doc.get("schema_version") or 1),
    }


def load_file(path: Path) -> Optional[dict[str, Any]]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Не удалось прочитать слепок %s: %s", path.name, exc)
        return None
    if not isinstance(doc, dict) or not doc.get("id"):
        return None
    return doc


def load_documents(dir_path: Optional[Path] = None) -> dict[str, dict[str, Any]]:
    """Читает все локальные слепки: {id: doc}."""
    root = Path(dir_path or config.SNAPSHOTS_DIR)
    if not root.exists():
        return {}
    docs: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("*.json")):
        doc = load_file(path)
        if doc and doc["id"] not in docs:
            docs[doc["id"]] = doc
    return docs
