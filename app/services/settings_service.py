from __future__ import annotations

import json
from typing import Any

from .. import config, database
from ..schemas import SettingsOut, SettingsUpdate


def _row_to_settings(row: Any) -> SettingsOut:
    try:
        defaults = json.loads(row["default_templates_json"] or "{}")
    except json.JSONDecodeError:
        defaults = {}
    return SettingsOut(
        provider=row["provider"],
        base_url=row["base_url"],
        api_key=row["api_key"],
        model=row["model"],
        temperature=row["temperature"],
        top_p=row["top_p"],
        seed=row["seed"],
        max_tokens=row["max_tokens"],
        timeout_seconds=row["timeout_seconds"],
        json_mode=bool(row["json_mode"]),
        max_input_chars=row["max_input_chars"],
        max_chunk_chars=row["max_chunk_chars"],
        default_templates=defaults,
    )


def get_settings() -> SettingsOut:
    with database.db() as conn:
        row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    if not row:
        database.init_db()
        with database.db() as conn:
            row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    return _row_to_settings(row)


def update_settings(payload: SettingsUpdate) -> SettingsOut:
    provider = payload.provider if payload.provider in config.PROVIDERS else "ollama"
    base_url = (payload.base_url or "").strip()
    if not base_url:
        base_url = config.DEFAULT_BASE_URLS[provider]
    defaults = {k: v for k, v in payload.default_templates.items() if v}
    with database.db() as conn:
        conn.execute(
            """
            UPDATE settings SET
              provider = ?, base_url = ?, api_key = ?, model = ?, temperature = ?,
              top_p = ?, seed = ?, max_tokens = ?, timeout_seconds = ?, json_mode = ?,
              max_input_chars = ?, max_chunk_chars = ?, default_templates_json = ?, updated_at = ?
            WHERE id = 1
            """,
            (
                provider,
                base_url,
                payload.api_key or "",
                payload.model or "",
                payload.temperature,
                payload.top_p,
                payload.seed,
                payload.max_tokens,
                payload.timeout_seconds,
                1 if payload.json_mode else 0,
                payload.max_input_chars,
                payload.max_chunk_chars,
                json.dumps(defaults, ensure_ascii=False),
                database.now_iso(),
            ),
        )
    return get_settings()


def active_template_id(snapshot_type: str) -> int | None:
    settings = get_settings()
    template_id = settings.default_templates.get(snapshot_type)
    if not template_id:
        return None
    with database.db() as conn:
        row = conn.execute(
            "SELECT id FROM templates WHERE id = ? AND enabled = 1", (template_id,)
        ).fetchone()
    return row["id"] if row else None
