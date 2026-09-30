from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import database
from app.services import snapshot_generator, snapshot_search


def _iso(days_ago: int = 0) -> str:
    return (
        (datetime.now(timezone.utc) - timedelta(days=days_ago))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _insert(
    directory: str,
    type_: str = "article",
    title: str = "Title",
    summary: str = "summary",
    search_text: str = "ollama privacy",
    confidence: float = 0.8,
    provider: str = "ollama",
    model: str = "llama3.1:8b",
    updated_at: str | None = None,
) -> str:
    snapshot_id = snapshot_generator.make_snapshot_id(directory, type_)
    ts = updated_at or _iso(0)
    with database.db() as conn:
        conn.execute("DELETE FROM snapshots WHERE snapshot_id = ?", (snapshot_id,))
        conn.execute(
            """
            INSERT INTO snapshots (snapshot_id, directory_path, normalized_directory, snapshot_type,
              template_id, template_name, provider, model, status, title, summary, sections_json,
              facts_json, highlights_json, entities_json, questions_json, tags_json, confidence,
              content_hash, original_chars, snapshot_chars, file_count, files_json,
              content_truncated, search_text, created_at, updated_at)
            VALUES (?, ?, ?, ?, NULL, 'T', ?, ?, 'success', ?, ?, '[]', ?, '[]', '{}', '[]', ?, ?,
              'sha256:x', 100, 50, 1, '[]', 0, ?, ?, ?)
            """,
            (
                snapshot_id, directory, directory, type_, provider, model, title, summary,
                json.dumps([{"id": "f1", "claim": "c", "quote": "q", "verified": True}]),
                json.dumps(["tag"]), confidence, search_text, ts, ts,
            ),
        )
        if database.fts_available(conn):
            conn.execute("DELETE FROM snapshots_fts WHERE snapshot_id = ?", (snapshot_id,))
            conn.execute(
                """INSERT INTO snapshots_fts (snapshot_id, title, directory, search_text, summary,
                   facts_text, tags_text, questions_text)
                   VALUES (?, ?, ?, ?, ?, '', '', '')""",
                (snapshot_id, title, directory, f"{title} {summary} {search_text}", summary),
            )
    return snapshot_id


@pytest.fixture(autouse=True)
def _clean():
    yield
    with database.db() as conn:
        conn.execute("DELETE FROM snapshots")
        if database.fts_available(conn):
            conn.execute("DELETE FROM snapshots_fts")


def test_query_match():
    _insert("/docs/a", title="Privacy of local LLM", search_text="ollama privacy local")
    result = snapshot_search.search_snapshots(query="privacy")
    assert result["total"] == 1
    assert result["items"][0]["title"] == "Privacy of local LLM"


def test_empty_query_returns_all():
    _insert("/docs/b")
    result = snapshot_search.search_snapshots(query="")
    assert result["total"] >= 1


def test_type_filter():
    _insert("/docs/c", type_="article")
    _insert("/docs/d", type_="notes")
    result = snapshot_search.search_snapshots(query="", type_="notes")
    assert result["total"] == 1
    assert result["items"][0]["type"] == "notes"


def test_provider_filter():
    _insert("/docs/e", provider="ollama")
    _insert("/docs/f", provider="lmstudio")
    result = snapshot_search.search_snapshots(query="", provider="lmstudio")
    assert result["total"] == 1
    assert result["items"][0]["provider"] == "lmstudio"


def test_min_confidence_filter():
    _insert("/docs/g", confidence=0.9)
    _insert("/docs/h", confidence=0.3)
    result = snapshot_search.search_snapshots(query="", min_confidence=0.5)
    assert result["total"] == 1
    assert result["items"][0]["confidence"] == pytest.approx(0.9)


def test_max_age_days_filter():
    _insert("/docs/i", updated_at=_iso(0))
    _insert("/docs/j", type_="news", updated_at=_iso(30))
    result = snapshot_search.search_snapshots(query="", max_age_days=7)
    assert result["total"] == 1
    assert result["items"][0]["type"] == "article"


def test_no_results():
    _insert("/docs/k")
    result = snapshot_search.search_snapshots(query="absolutely-unique-nothing-123")
    assert result["total"] == 0
    assert result["items"] == []


def test_verified_facts_counted():
    sid = _insert("/docs/l")
    result = snapshot_search.search_snapshots(query="")
    item = next(i for i in result["items"] if i["snapshot_id"] == sid)
    assert item["verified_facts"] == 1
    assert item["total_facts"] == 1


def test_delete_snapshot_removes_file_and_row(tmp_path: Path):
    sid = _insert("/docs/m")
    path = database.config.SNAPSHOTS_DIR / f"{sid}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    assert snapshot_search.delete_snapshot(sid) is True
    assert snapshot_search.get_snapshot(sid) is None
    assert not path.exists()
