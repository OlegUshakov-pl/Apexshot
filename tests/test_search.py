from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
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


# =====================================================================
# Гибридный поиск (ChromaDB + BM25 + RRF)
# =====================================================================

from app.search import (  # noqa: E402
    bm25_index,
    hybrid_search,
    search_status,
    vector_index,
)
from app.search.ollama_client import OllamaClient, set_client  # noqa: E402

DIM = 16


def _hash_vector(text: str) -> list[float]:
    vec = [0.0] * DIM
    for token in bm25_index.tokenize(text):
        import hashlib

        digest = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        vec[digest % DIM] += 1.0
    return vec


def _ollama_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/tags":
        return httpx.Response(200, json={"models": [{"name": "bge-m3"}]})
    if request.url.path == "/api/embed":
        body = json.loads(request.read().decode("utf-8"))
        texts = body.get("input") or []
        if isinstance(texts, str):
            texts = [texts]
        return httpx.Response(
            200, json={"embeddings": [_hash_vector(t) for t in texts]}
        )
    return httpx.Response(404, json={})


def _broken_handler(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("Ollama down")


def _snapshot_doc(
    snap_id: str,
    title: str,
    summary: str,
    facts: list[dict],
    entities: dict | None = None,
    url: str = "https://example.com",
) -> dict:
    return {
        "id": snap_id,
        "title": title,
        "summary": summary,
        "facts": facts,
        "entities": entities or {},
        "tags": [],
        "source_url": url,
        "fetched_at": "2025-01-01T00:00:00Z",
        "provider": "ollama",
        "model": "llama3.2:3b",
        "schema_version": 1,
    }


def _write_snapshots(dir_path: Path, docs: list[dict]) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    for doc in docs:
        (dir_path / f"{doc['id']}.json").write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8"
        )


@pytest.fixture()
def _hybrid_env(monkeypatch):
    """Изолированное состояние гибридного поиска: свежие файлы + мок Ollama."""
    config = database.config
    chroma_dir = config.SNAPSHOTS_DIR.parent / "chroma_test"
    monkeypatch.setattr(config, "CHROMA_DIR", chroma_dir, raising=False)
    vector_index.reset()
    set_client(OllamaClient(transport=httpx.MockTransport(_ollama_handler)))
    yield config
    # расшаренное состояние между тестами не течёт
    set_client(None)
    vector_index.reset()
    if chroma_dir.exists():
        import shutil

        shutil.rmtree(chroma_dir, ignore_errors=True)


_SNAPSHOTS = [
    _snapshot_doc(
        "snap-aaa",
        "Ollama privacy guide",
        "Running local LLMs privately with Ollama on your machine",
        [
            {"claim": "Ollama stores data locally", "quote": "data never leaves the host"},
        ],
        {"topics": ["privacy"], "technologies": ["ollama"]},
        "https://example.com/ollama",
    ),
    _snapshot_doc(
        "snap-bbb",
        "FastAPI tutorial",
        "Building HTTP APIs with FastAPI and Python",
        [
            {"claim": "FastAPI supports async handlers", "quote": "async def route()"},
        ],
        {"topics": ["api"], "technologies": ["fastapi", "python"]},
    ),
    _snapshot_doc(
        "snap-ccc",
        "Django basics",
        "Django ORM models and migrations explained",
        [
            {"claim": "Django migrations persist schema", "quote": "python manage.py migrate"},
        ],
        {"topics": ["orm"], "technologies": ["django"]},
    ),
]


def _rebuild(config) -> None:
    for stale in config.SNAPSHOTS_DIR.glob("*.json"):
        stale.unlink()
    _write_snapshots(config.SNAPSHOTS_DIR, list(_SNAPSHOTS))
    from app import search as search_module

    search_module.rebuild_search_index()


def test_hybrid_returns_expected_ids(_hybrid_env):
    config = _hybrid_env
    _rebuild(config)
    results = hybrid_search("ollama privacy", top_k=3)
    ids = [r["id"] for r in results]
    assert "snap-aaa" in ids
    top = results[0]
    assert top["id"] == "snap-aaa"
    for key in ("id", "title", "summary", "source_url", "score",
                "matched_fields", "snippet", "degraded"):
        assert key in top
    assert top["degraded"] is False
    assert "vector" in results[0]["matched_fields"]
    assert results[0]["snippet"].strip()


def test_ollama_down_degrades_to_bm25(_hybrid_env):
    config = _hybrid_env
    _write_snapshots(config.SNAPSHOTS_DIR, list(_SNAPSHOTS))
    # «Ollama упала»: любой запрос к ней кидает ConnectError
    set_client(OllamaClient(transport=httpx.MockTransport(_broken_handler)))
    from app import search as search_module

    search_module.rebuild_search_index()
    assert search_module.degraded() is True

    results = hybrid_search("fastapi async", top_k=5)
    ids = [r["id"] for r in results]
    assert "snap-bbb" in ids
    assert all(r["degraded"] is True for r in results)
    assert all("vector" not in r["matched_fields"] for r in results)
    status = search_status()
    assert status["ollama"]["available"] is False


def test_rrf_doc_in_both_lists_scores_higher(_hybrid_env):
    from app.search.fusion import rrf_merge

    vector_list = [("a", 0.9), ("b", 0.8), ("c", 0.7)]
    bm25_list = [("b", 12.0), ("a", 10.0), ("d", 5.0)]
    fused = dict(rrf_merge(vector_list, bm25_list))
    # a и b есть в обоих; c и d — только в одном
    assert fused["a"] > fused["c"]
    assert fused["b"] > fused["d"]
    assert fused["a"] > fused["d"]


def test_new_snapshot_appears_in_results(_hybrid_env):
    config = _hybrid_env
    _rebuild(config)
    new_doc = _snapshot_doc(
        "snap-ddd",
        "Vector databases overview",
        "ChromaDB stores embeddings locally",
        [{"claim": "ChromaDB is embedded", "quote": "pip install chromadb"}],
        {"technologies": ["chromadb"]},
    )
    _write_snapshots(config.SNAPSHOTS_DIR, [new_doc])
    from app import search as search_module

    search_module.on_snapshot_saved("snap-ddd")

    results = hybrid_search("chromadb embeddings", top_k=5)
    ids = [r["id"] for r in results]
    assert "snap-ddd" in ids
    assert bm25_index.get_doc("snap-ddd") is not None


def test_deleted_snapshot_disappears(_hybrid_env):
    config = _hybrid_env
    _rebuild(config)
    victim = config.SNAPSHOTS_DIR / "snap-bbb.json"
    victim.unlink()
    from app import search as search_module

    search_module.on_snapshot_deleted("snap-bbb")

    results = hybrid_search("fastapi", top_k=10)
    assert "snap-bbb" not in [r["id"] for r in results]
    assert bm25_index.get_doc("snap-bbb") is None


def test_api_search_endpoint(_hybrid_env):
    from fastapi.testclient import TestClient

    config = _hybrid_env
    _rebuild(config)
    from app.main import app

    with TestClient(app) as client:
        resp = client.post("/api/search", json={"query": "ollama", "top_k": 3})
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) >= {"results", "total", "search_ms"}
    assert data["total"] == len(data["results"])
    for item in data["results"]:
        assert {"id", "title", "score", "degraded"} <= set(item.keys())
        assert item["degraded"] is False
