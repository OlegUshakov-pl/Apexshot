from __future__ import annotations

import json
from typing import Any, Optional

from .. import config, database
from ..schemas import TemplateIn, TemplateOut


class TemplateError(ValueError):
    pass


def _row_to_out(row: Any) -> TemplateOut:
    return TemplateOut(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        snapshot_type=row["snapshot_type"],
        system_prompt=row["system_prompt"],
        user_prompt=row["user_prompt"],
        chunk_user_prompt=row["chunk_user_prompt"],
        merge_user_prompt=row["merge_user_prompt"],
        schema_json=row["schema_json"],
        enabled=bool(row["enabled"]),
        is_default=bool(row["is_default"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _validate(payload: TemplateIn) -> None:
    if not payload.name.strip():
        raise TemplateError("Название шаблона не может быть пустым")
    if payload.snapshot_type not in config.SNAPSHOT_TYPES:
        raise TemplateError(
            f"Недопустимый тип слепка: {payload.snapshot_type}. "
            f"Допустимые: {', '.join(config.SNAPSHOT_TYPES)}"
        )
    if not payload.system_prompt.strip():
        raise TemplateError("system prompt не может быть пустым")
    if not payload.user_prompt.strip():
        raise TemplateError("user prompt не может быть пустым")
    try:
        parsed = json.loads(payload.schema_json or "{}")
    except json.JSONDecodeError as exc:
        raise TemplateError(f"schema_json — не валидный JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise TemplateError("schema_json должен быть JSON-объектом")


def list_templates(
    snapshot_type: Optional[str] = None, enabled: Optional[bool] = None
) -> list[TemplateOut]:
    sql = "SELECT * FROM templates"
    clauses: list[str] = []
    params: list[Any] = []
    if snapshot_type:
        clauses.append("snapshot_type = ?")
        params.append(snapshot_type)
    if enabled is not None:
        clauses.append("enabled = ?")
        params.append(1 if enabled else 0)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY snapshot_type, id"
    with database.db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_out(r) for r in rows]


def get_template(template_id: int) -> Optional[TemplateOut]:
    with database.db() as conn:
        row = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,)).fetchone()
    return _row_to_out(row) if row else None


def create_template(payload: TemplateIn) -> TemplateOut:
    _validate(payload)
    ts = database.now_iso()
    with database.db() as conn:
        cur = conn.execute(
            """
            INSERT INTO templates (name, description, snapshot_type, system_prompt, user_prompt,
              chunk_user_prompt, merge_user_prompt, schema_json, enabled, is_default,
              created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.name.strip(),
                payload.description,
                payload.snapshot_type,
                payload.system_prompt,
                payload.user_prompt,
                payload.chunk_user_prompt,
                payload.merge_user_prompt,
                payload.schema_json,
                1 if payload.enabled else 0,
                1 if payload.is_default else 0,
                ts,
                ts,
            ),
        )
        template_id = int(cur.lastrowid)
    if payload.is_default:
        set_default(template_id, payload.snapshot_type)
    return get_template(template_id)  # type: ignore[return-value]


def update_template(template_id: int, payload: TemplateIn) -> Optional[TemplateOut]:
    if get_template(template_id) is None:
        return None
    _validate(payload)
    with database.db() as conn:
        conn.execute(
            """
            UPDATE templates SET
              name = ?, description = ?, snapshot_type = ?, system_prompt = ?, user_prompt = ?,
              chunk_user_prompt = ?, merge_user_prompt = ?, schema_json = ?, enabled = ?,
              is_default = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.name.strip(),
                payload.description,
                payload.snapshot_type,
                payload.system_prompt,
                payload.user_prompt,
                payload.chunk_user_prompt,
                payload.merge_user_prompt,
                payload.schema_json,
                1 if payload.enabled else 0,
                1 if payload.is_default else 0,
                database.now_iso(),
                template_id,
            ),
        )
    if payload.is_default:
        set_default(template_id, payload.snapshot_type)
    return get_template(template_id)


def delete_template(template_id: int) -> bool:
    template = get_template(template_id)
    if not template:
        return False
    with database.db() as conn:
        conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
        defaults = _load_defaults(conn)
        if defaults.get(template.snapshot_type) == template_id:
            fallback = conn.execute(
                "SELECT id FROM templates WHERE snapshot_type = ? AND enabled = 1 AND id != ? ORDER BY id LIMIT 1",
                (template.snapshot_type, template_id),
            ).fetchone()
            if fallback:
                defaults[template.snapshot_type] = fallback["id"]
            else:
                defaults.pop(template.snapshot_type, None)
            conn.execute(
                "UPDATE settings SET default_templates_json = ? WHERE id = 1",
                (json.dumps(defaults, ensure_ascii=False),),
            )
    return True


def set_default(template_id: int, snapshot_type: Optional[str] = None) -> None:
    template = get_template(template_id)
    if not template:
        raise TemplateError("Шаблон не найден")
    type_key = snapshot_type or template.snapshot_type
    with database.db() as conn:
        conn.execute(
            "UPDATE templates SET is_default = CASE WHEN id = ? THEN 1 ELSE 0 END, updated_at = ?",
            (template_id, database.now_iso()),
        )
        conn.execute(
            "UPDATE templates SET is_default = 0 WHERE snapshot_type = ? AND id != ?",
            (type_key, template_id),
        )
        defaults = _load_defaults(conn)
        defaults[type_key] = template_id
        conn.execute(
            "UPDATE settings SET default_templates_json = ? WHERE id = 1",
            (json.dumps(defaults, ensure_ascii=False),),
        )


def toggle_enabled(template_id: int, enabled: bool) -> Optional[TemplateOut]:
    template = get_template(template_id)
    if not template:
        return None
    with database.db() as conn:
        conn.execute(
            "UPDATE templates SET enabled = ?, updated_at = ? WHERE id = ?",
            (1 if enabled else 0, database.now_iso(), template_id),
        )
    return get_template(template_id)


def _load_defaults(conn: Any) -> dict:
    row = conn.execute("SELECT default_templates_json FROM settings WHERE id = 1").fetchone()
    if not row:
        return {}
    try:
        return json.loads(row["default_templates_json"] or "{}")
    except json.JSONDecodeError:
        return {}


def get_active_template(snapshot_type: str) -> Optional[TemplateOut]:
    template_id = _active_template_id(snapshot_type)
    if not template_id:
        return None
    template = get_template(template_id)
    if template and template.enabled:
        return template
    fallback = [t for t in list_templates(snapshot_type, enabled=True)]
    return fallback[0] if fallback else None


def _active_template_id(snapshot_type: str) -> Optional[int]:
    with database.db() as conn:
        row = conn.execute("SELECT default_templates_json FROM settings WHERE id = 1").fetchone()
    if not row:
        return None
    try:
        defaults = json.loads(row["default_templates_json"] or "{}")
    except json.JSONDecodeError:
        return None
    value = defaults.get(snapshot_type)
    return int(value) if value else None


def usage_warnings(template: TemplateOut) -> list[str]:
    warnings: list[str] = []
    active_id = _active_template_id(template.snapshot_type)
    if active_id == template.id:
        warnings.append(
            f"Этот шаблон используется как активный для типа {template.snapshot_type}"
        )
    return warnings
