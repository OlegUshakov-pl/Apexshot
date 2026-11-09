from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from .. import config, database
from ..models import is_valid_source_url, normalize_directory, normalize_source_url
from .snapshot_generator import make_snapshot_id


def _tokens(query: str) -> list[str]:
    return [t for t in re.split(r"\s+", (query or "").strip()) if t]


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _fts_query(query: str) -> str:
    parts = []
    for token in _tokens(query):
        cleaned = token.replace('"', " ").strip()
        if cleaned:
            parts.append(f'"{cleaned}"')
    return " AND ".join(parts)


def _filter_clause(
    type_: Optional[str],
    provider: Optional[str],
    model: Optional[str],
    template_id: Optional[int],
    min_confidence: Optional[float],
    max_age_days: Optional[int],
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if type_:
        clauses.append("snapshot_type = ?")
        params.append(type_)
    if provider:
        clauses.append("provider = ?")
        params.append(provider)
    if model:
        clauses.append("model = ?")
        params.append(model)
    if template_id:
        clauses.append("template_id = ?")
        params.append(template_id)
    if min_confidence is not None:
        clauses.append("confidence >= ?")
        params.append(min_confidence)
    if max_age_days is not None:
        since = (
            datetime.now(timezone.utc) - timedelta(days=int(max_age_days))
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        clauses.append("updated_at >= ?")
        params.append(since)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def search_snapshots(
    query: str = "",
    type_: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    template_id: Optional[int] = None,
    min_confidence: Optional[float] = None,
    max_age_days: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 20), 100))
    offset = max(0, int(offset or 0))
    tokens = _tokens(query)
    rows: list[sqlite3.Row]
    total: int
    snippets: dict[str, str] = {}
    matched: list[str] = []

    with database.db() as conn:
        where, params = _filter_clause(
            type_, provider, model, template_id, min_confidence, max_age_days
        )
        if not tokens:
            count_sql = f"SELECT COUNT(*) AS c FROM snapshots{where}"
            total = conn.execute(count_sql, params).fetchone()["c"]
            rows = conn.execute(
                f"SELECT * FROM snapshots{where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
        elif database.fts_available(conn):
            match = _fts_query(query)
            try:
                hits = conn.execute(
                    """
                    SELECT snapshot_id, rank,
                           snippet(snapshots_fts, 4, '<mark>', '</mark>', '…', 16) AS snip
                    FROM snapshots_fts
                    WHERE snapshots_fts MATCH ?
                    ORDER BY rank
                    LIMIT 1000
                    """,
                    (match,),
                ).fetchall()
            except sqlite3.OperationalError:
                hits = []
            if hits:
                order = {h["snapshot_id"]: i for i, h in enumerate(hits)}
                snippets = {h["snapshot_id"]: h["snip"] or "" for h in hits}
                ids = list(order.keys())
                placeholders = ",".join("?" for _ in ids)
                base = (
                    f"SELECT * FROM snapshots{where}"
                    + (f" AND snapshot_id IN ({placeholders})" if where else
                       f" WHERE snapshot_id IN ({placeholders})")
                )
                candidates = conn.execute(base, [*params, *ids]).fetchall()
                candidates.sort(key=lambda r: order.get(r["snapshot_id"], 10**9))
                total = len(candidates)
                rows = candidates[offset : offset + limit]
            else:
                rows, total = _like_search(
                    conn, query, where, params, limit, offset
                )
        else:
            rows, total = _like_search(conn, query, where, params, limit, offset)

    matched = [t for t in tokens if t.lower() not in ("or", "and", "not")]
    items = []
    for row in rows:
        facts = _safe_json(row["facts_json"], [])
        verified = sum(1 for f in facts if isinstance(f, dict) and f.get("verified"))
        snippet = snippets.get(row["snapshot_id"], "")
        if not snippet:
            snippet = row["summary"] or ""
        items.append(
            {
                "snapshot_id": row["snapshot_id"],
                "title": row["title"],
                "directory": row["directory_path"],
                "source_url": row["source_url"] if "source_url" in row.keys() else "",
                "type": row["snapshot_type"],
                "summary": row["summary"],
                "confidence": row["confidence"],
                "provider": row["provider"],
                "model": row["model"],
                "template_name": row["template_name"],
                "tags": _safe_json(row["tags_json"], []),
                "updated_at": row["updated_at"],
                "snippet": snippet,
                "verified_facts": verified,
                "total_facts": len(facts),
            }
        )
    return {"total": total, "limit": limit, "offset": offset, "items": items, "matched": matched}


def _like_search(
    conn: sqlite3.Connection,
    query: str,
    where: str,
    params: list[Any],
    limit: int,
    offset: int,
) -> tuple[list[sqlite3.Row], int]:
    tokens = _tokens(query)
    clauses: list[str] = []
    like_params: list[Any] = []
    for token in tokens:
        pattern = f"%{_escape_like(token)}%"
        clauses.append(
            "(search_text LIKE ? ESCAPE '\\' OR title LIKE ? ESCAPE '\\' "
            "OR summary LIKE ? ESCAPE '\\')"
        )
        like_params.extend([pattern, pattern, pattern])
    if not clauses:
        return [], 0
    joiner = " WHERE " if not where else " AND "
    full_where = where + joiner + " AND ".join(clauses)
    count = conn.execute(
        f"SELECT COUNT(*) AS c FROM snapshots{full_where}", [*params, *like_params]
    ).fetchone()["c"]
    rows = conn.execute(
        f"SELECT * FROM snapshots{full_where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        [*params, *like_params, limit, offset],
    ).fetchall()
    return rows, count


def get_snapshot(snapshot_id: str) -> Optional[dict[str, Any]]:
    with database.db() as conn:
        row = conn.execute(
            "SELECT * FROM snapshots WHERE snapshot_id = ?", (snapshot_id,)
        ).fetchone()
    if not row:
        return None
    data = dict(row)
    facts = _safe_json(data.get("facts_json"), [])
    data["verified_facts"] = sum(
        1 for f in facts if isinstance(f, dict) and f.get("verified")
    )
    data["total_facts"] = len(facts)
    return data


def read_raw(snapshot_id: str) -> Optional[dict[str, Any]]:
    path = config.SNAPSHOTS_DIR / f"{snapshot_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def delete_snapshot(snapshot_id: str) -> bool:
    with database.db() as conn:
        row = conn.execute(
            "SELECT id FROM snapshots WHERE snapshot_id = ?", (snapshot_id,)
        ).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM snapshots WHERE snapshot_id = ?", (snapshot_id,))
        if database.fts_available(conn):
            conn.execute(
                "DELETE FROM snapshots_fts WHERE snapshot_id = ?", (snapshot_id,)
            )
        conn.execute(
            "UPDATE jobs SET status = 'cancelled' WHERE snapshot_id = ? AND status IN ('pending','processing')",
            (snapshot_id,),
        )
    path = config.SNAPSHOTS_DIR / f"{snapshot_id}.json"
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
    try:
        from .. import search

        search.on_snapshot_deleted(snapshot_id)
    except Exception:  # noqa: BLE001 — удаление не должно падать из-за индекса
        pass
    return True


def exists_for_directory(directory: str, snapshot_type: str) -> Optional[str]:
    raw = (directory or "").strip().strip('"')
    if is_valid_source_url(raw):
        norm = normalize_source_url(raw)
    elif Path(raw).exists():
        norm = normalize_directory(str(Path(raw).resolve()))
    else:
        norm = normalize_directory(raw)
    snapshot_id = make_snapshot_id(norm, snapshot_type)
    snapshot = get_snapshot(snapshot_id)
    return snapshot_id if snapshot else None


def stats() -> dict[str, Any]:
    with database.db() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM snapshots").fetchone()["c"]
        success = conn.execute(
            "SELECT COUNT(*) AS c FROM snapshots WHERE status = 'success'"
        ).fetchone()["c"]
        by_type_rows = conn.execute(
            "SELECT snapshot_type, COUNT(*) AS c FROM snapshots GROUP BY snapshot_type"
        ).fetchall()
        templates = conn.execute("SELECT COUNT(*) AS c FROM templates").fetchone()["c"]
        job_failed = conn.execute(
            "SELECT COUNT(*) AS c FROM jobs WHERE status = 'failed'"
        ).fetchone()["c"]
    return {
        "total": total,
        "success": success,
        "failed": job_failed,
        "by_type": {r["snapshot_type"]: r["c"] for r in by_type_rows},
        "template_count": templates,
    }


def recent(limit: int = 5) -> list[dict[str, Any]]:
    with database.db() as conn:
        rows = conn.execute(
            "SELECT * FROM snapshots ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
    result = []
    for row in rows:
        data = dict(row)
        facts = _safe_json(data.get("facts_json"), [])
        data["verified_facts"] = sum(
            1 for f in facts if isinstance(f, dict) and f.get("verified")
        )
        data["total_facts"] = len(facts)
        result.append(data)
    return result


def distinct_models() -> list[str]:
    with database.db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT model FROM snapshots WHERE model != '' ORDER BY model"
        ).fetchall()
    return [r["model"] for r in rows]


def _safe_json(value: Any, default: Any) -> Any:
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value or "")
    except (json.JSONDecodeError, TypeError, ValueError):
        return default
