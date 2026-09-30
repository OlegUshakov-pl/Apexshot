from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from . import config
from .default_prompts import build_default_templates

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS settings (
  id INTEGER PRIMARY KEY,
  provider TEXT NOT NULL DEFAULT 'ollama',
  base_url TEXT NOT NULL,
  api_key TEXT NOT NULL DEFAULT '',
  model TEXT NOT NULL,
  temperature REAL NOT NULL DEFAULT 0.1,
  top_p REAL NOT NULL DEFAULT 0.9,
  seed INTEGER NOT NULL DEFAULT 42,
  max_tokens INTEGER NOT NULL DEFAULT 2000,
  timeout_seconds INTEGER NOT NULL DEFAULT 300,
  json_mode INTEGER NOT NULL DEFAULT 1,
  max_input_chars INTEGER NOT NULL DEFAULT 12000,
  max_chunk_chars INTEGER NOT NULL DEFAULT 6000,
  default_templates_json TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS templates (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  snapshot_type TEXT NOT NULL,
  system_prompt TEXT NOT NULL,
  user_prompt TEXT NOT NULL,
  chunk_user_prompt TEXT NOT NULL DEFAULT '',
  merge_user_prompt TEXT NOT NULL DEFAULT '',
  schema_json TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  is_default INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY,
  snapshot_id TEXT NOT NULL UNIQUE,
  directory_path TEXT NOT NULL,
  normalized_directory TEXT NOT NULL,
  snapshot_type TEXT NOT NULL,
  template_id INTEGER,
  template_name TEXT,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  error TEXT,
  title TEXT,
  summary TEXT,
  sections_json TEXT NOT NULL DEFAULT '[]',
  facts_json TEXT NOT NULL DEFAULT '[]',
  highlights_json TEXT NOT NULL DEFAULT '[]',
  entities_json TEXT NOT NULL DEFAULT '{}',
  questions_json TEXT NOT NULL DEFAULT '[]',
  tags_json TEXT NOT NULL DEFAULT '[]',
  confidence REAL NOT NULL DEFAULT 0.0,
  content_hash TEXT,
  original_chars INTEGER NOT NULL DEFAULT 0,
  snapshot_chars INTEGER NOT NULL DEFAULT 0,
  file_count INTEGER NOT NULL DEFAULT 0,
  files_json TEXT NOT NULL DEFAULT '[]',
  content_truncated INTEGER NOT NULL DEFAULT 0,
  search_text TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshots_directory_type
ON snapshots(normalized_directory, snapshot_type);

CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY,
  snapshot_type TEXT NOT NULL,
  directory_path TEXT NOT NULL,
  template_id INTEGER,
  status TEXT NOT NULL DEFAULT 'pending',
  progress INTEGER NOT NULL DEFAULT 0,
  step TEXT NOT NULL DEFAULT 'queued',
  error TEXT,
  snapshot_id TEXT,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT
);
"""

FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS snapshots_fts
USING fts5(
  snapshot_id,
  title,
  directory,
  search_text,
  summary,
  facts_text,
  tags_text,
  questions_text
);
"""

_fts_ok: bool | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def connect() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DB_PATH), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fts_available(conn: sqlite3.Connection | None = None) -> bool:
    global _fts_ok
    if _fts_ok is not None:
        return _fts_ok
    own = conn is None
    conn = conn or connect()
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS tmp_fts_probe USING fts5(x)")
        conn.execute("DROP TABLE IF EXISTS tmp_fts_probe")
        _fts_ok = True
    except sqlite3.OperationalError:
        _fts_ok = False
    finally:
        if own:
            conn.close()
    return _fts_ok


def init_db() -> None:
    config.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.executescript(SCHEMA_SQL)
        if fts_available(conn):
            conn.executescript(FTS_SQL)
        _seed_settings(conn)
        _seed_templates(conn)


def _seed_settings(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT id FROM settings WHERE id = 1").fetchone()
    if row:
        return
    defaults = dict(config.DEFAULTS)
    conn.execute(
        """
        INSERT INTO settings (id, provider, base_url, api_key, model, temperature, top_p,
          seed, max_tokens, timeout_seconds, json_mode, max_input_chars, max_chunk_chars,
          default_templates_json, updated_at)
        VALUES (1, :provider, :base_url, :api_key, :model, :temperature, :top_p,
          :seed, :max_tokens, :timeout_seconds, :json_mode, :max_input_chars, :max_chunk_chars,
          :default_templates_json, :updated_at)
        """,
        {**defaults, "updated_at": now_iso()},
    )


def _seed_templates(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) AS c FROM templates").fetchone()["c"]
    if count:
        return
    ts = now_iso()
    defaults_row = conn.execute(
        "SELECT default_templates_json FROM settings WHERE id = 1"
    ).fetchone()
    defaults = json.loads(defaults_row["default_templates_json"] or "{}")
    for tpl in build_default_templates():
        cur = conn.execute(
            """
            INSERT INTO templates (name, description, snapshot_type, system_prompt, user_prompt,
              chunk_user_prompt, merge_user_prompt, schema_json, enabled, is_default,
              created_at, updated_at)
            VALUES (:name, :description, :snapshot_type, :system_prompt, :user_prompt,
              :chunk_user_prompt, :merge_user_prompt, :schema_json, :enabled, :is_default, :ts, :ts)
            """,
            {**tpl, "ts": ts},
        )
        defaults.setdefault(tpl["snapshot_type"], cur.lastrowid)
    conn.execute(
        "UPDATE settings SET default_templates_json = ? WHERE id = 1",
        (json.dumps(defaults, ensure_ascii=False),),
    )
