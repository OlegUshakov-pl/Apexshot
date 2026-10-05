from __future__ import annotations

import json

from app import config, database
from app.models import is_local_url, is_valid_source_url, normalize_source_url
from app.services import snapshot_generator as sg
from app.services import snapshot_sender, snapshot_search, template_service


def test_source_url_helpers():
    assert is_valid_source_url("https://github.com/user/repo")
    assert is_valid_source_url("http://example.com/page")
    assert not is_valid_source_url("ftp://example.com/x")
    assert not is_valid_source_url("not a url")
    assert not is_valid_source_url("")
    assert not is_local_url("https://github.com/user/repo")
    assert not is_local_url("")
    assert is_local_url("http://localhost:8000/x")
    assert is_local_url("http://127.0.0.1/")
    assert is_local_url("https://127.0.0.5/abc")
    assert normalize_source_url("https://GitHub.com/User/Repo/") == "https://github.com/User/Repo"
    assert normalize_source_url("  ") == ""


def _valid_llm_doc():
    return json.dumps(
        {
            "title": "Page title",
            "summary": "Page summary",
            "facts": [{"id": "f1", "claim": "c", "quote": "Some page text", "confidence": 0.9}],
            "confidence": 0.9,
        }
    )


def test_url_pipeline_saves_source_url(monkeypatch):
    url = "https://example.com/page"
    monkeypatch.setattr(
        sg.text_extractor,
        "fetch_url_text",
        lambda u, timeout=30.0: ("Page title", "Some page text here", url),
    )
    monkeypatch.setattr(sg, "_call_llm", lambda *a, **k: _valid_llm_doc())
    template = template_service.get_active_template("webpage")
    assert template is not None
    job_id = sg.create_job("webpage", url, template.id, url)
    sg.run_job(job_id)
    job = sg.get_job(job_id)
    assert job is not None and job["status"] == "success", job
    snapshot_id = job["snapshot_id"]
    row = snapshot_search.get_snapshot(snapshot_id)
    assert row is not None and row["source_url"] == url
    raw = snapshot_search.read_raw(snapshot_id)
    assert raw is not None and raw["source_url"] == url
    assert url in (raw.get("search_text") or "")
    snapshot_search.delete_snapshot(snapshot_id)


def test_sender_blocks_empty_and_local_source_url(monkeypatch):
    monkeypatch.setattr(snapshot_sender, "read_raw", lambda sid: {"id": sid})
    monkeypatch.setattr(snapshot_sender, "get_snapshot", lambda sid: {"source_url": ""})
    res = snapshot_sender.send_snapshot("snap-x")
    assert res.ok is False

    monkeypatch.setattr(
        snapshot_sender, "read_raw", lambda sid: {"source_url": "http://localhost:8000/x"}
    )
    res = snapshot_sender.send_snapshot("snap-x", server_url="http://srv/hook")
    assert res.ok is False and (
        "localhost" in res.error or "локальный" in res.error
    )

    monkeypatch.setattr(
        snapshot_sender,
        "read_raw",
        lambda sid: {"source_url": "https://github.com/user/repo"},
    )

    class Resp:
        status_code = 200
        text = "ok"

    import httpx

    monkeypatch.setattr(httpx, "post", lambda *a, **k: Resp())
    res = snapshot_sender.send_snapshot("snap-x", server_url="http://srv/hook")
    assert res.ok is True and res.status_code == 200


def test_migrate_adds_source_url_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", tmp_path / "snapshots")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "snapshots.db")
    database._fts_ok = None
    database.init_db()
    # Имитируем старую БД: убираем колонки, затем прогоняем миграцию заново.
    with database.db() as conn:
        conn.execute("ALTER TABLE snapshots DROP COLUMN source_url")
        conn.execute("ALTER TABLE jobs DROP COLUMN source_url")
    with database.db() as conn:
        snap_cols = {r["name"] for r in conn.execute("PRAGMA table_info(snapshots)")}
        job_cols = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)")}
    assert "source_url" not in snap_cols
    assert "source_url" not in job_cols
    database._fts_ok = None
    database.init_db()
    with database.db() as conn:
        snap_cols = {r["name"] for r in conn.execute("PRAGMA table_info(snapshots)")}
        job_cols = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)")}
    assert "source_url" in snap_cols
    assert "source_url" in job_cols
    database._fts_ok = None
