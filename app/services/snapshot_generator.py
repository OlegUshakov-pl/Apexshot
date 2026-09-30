from __future__ import annotations

import hashlib
import json
import re
import traceback
from pathlib import Path
from typing import Any, Optional

from .. import config, database
from ..default_prompts import SNAPSHOT_SCHEMA
from ..models import normalize_directory
from . import llm_provider, settings_service, template_service, text_extractor


class JsonParseError(Exception):
    pass


class GenerationError(Exception):
    def __init__(self, message: str, detail: str = ""):
        super().__init__(detail or message)
        self.message = message
        self.detail = detail or message


MAX_ATTEMPTS = 3
STRICT_JSON_PREFIX = "Верни только JSON. Не добавляй markdown. Не добавляй пояснения.\n\n"
_PLACEHOLDER = re.compile(r"\{([a-zA-Z_]+)\}")


def make_snapshot_id(normalized_directory: str, snapshot_type: str) -> str:
    payload = f"{normalized_directory}:{snapshot_type}".encode("utf-8")
    return "snap-" + hashlib.sha256(payload).hexdigest()[:16]


def render_prompt(template: str, mapping: dict[str, Any]) -> str:
    def repl(match: re.Match) -> str:
        key = match.group(1)
        if key in mapping:
            return str(mapping[key])
        return match.group(0)

    return _PLACEHOLDER.sub(repl, template or "")


def parse_json_response(text: str) -> dict[str, Any]:
    if not text or not text.strip():
        raise JsonParseError("Пустой ответ модели")
    s = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", s, re.S | re.I)
    if fence:
        s = fence.group(1).strip()
    candidates = [s]
    start, end = s.find("{"), s.rfind("}")
    if 0 <= start < end:
        candidates.append(s[start : end + 1])
    for candidate in candidates:
        for attempt in (candidate, _strip_trailing_commas(candidate)):
            try:
                data = json.loads(attempt)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(data, dict):
                return data
    raise JsonParseError("Модель вернула невалидный JSON")


def _strip_trailing_commas(text: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", text)


def normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def verify_quotes(data: dict[str, Any], corpus: str) -> dict[str, Any]:
    corpus_norm = normalize_for_match(corpus)
    for fact in data.get("facts") or []:
        if not isinstance(fact, dict):
            continue
        quote = fact.get("quote") or ""
        found = bool(quote) and normalize_for_match(quote) in corpus_norm
        fact["verified"] = found
        if not found:
            try:
                conf = float(fact.get("confidence") or 0.0)
            except (TypeError, ValueError):
                conf = 0.0
            conf = round(max(0.0, conf - 0.2), 2)
            fact["confidence"] = conf
            fact["quality"] = "low_quality" if conf < 0.3 else "ok"
        else:
            fact.setdefault("quality", "ok")
    for highlight in data.get("highlights") or []:
        if not isinstance(highlight, dict):
            continue
        quote = highlight.get("quote") or ""
        highlight["verified"] = bool(quote) and normalize_for_match(quote) in corpus_norm
    return data


def chunk_text(text: str, max_chars: int) -> list[str]:
    if max_chars <= 0 or len(text) <= max_chars:
        return [text]
    parts: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        if len(current) + len(paragraph) + 2 > max_chars:
            if current:
                parts.append(current)
            current = ""
            while len(paragraph) > max_chars:
                parts.append(paragraph[:max_chars])
                paragraph = paragraph[max_chars:]
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        parts.append(current)
    return [p for p in parts if p.strip()]


def empty_partial() -> dict[str, Any]:
    return {
        "title": "",
        "summary": "",
        "sections": [],
        "facts": [],
        "highlights": [],
        "entities": {
            "topics": [],
            "organizations": [],
            "people": [],
            "technologies": [],
            "locations": [],
            "dates": [],
        },
        "questions": [],
        "tags": [],
        "confidence": 0.0,
    }


def normalize_snapshot_doc(data: dict[str, Any]) -> dict[str, Any]:
    doc = empty_partial()
    doc["title"] = str(data.get("title") or "").strip()
    doc["summary"] = str(data.get("summary") or "").strip()
    sections = data.get("sections") or []
    doc["sections"] = [
        {"heading": str(s.get("heading", "")), "text": str(s.get("text", ""))}
        for s in sections
        if isinstance(s, dict)
    ]
    facts = []
    for idx, fact in enumerate(data.get("facts") or [], start=1):
        if not isinstance(fact, dict):
            continue
        fact.setdefault("id", f"f{idx}")
        fact.setdefault("type", "inferred")
        fact.setdefault("file", "")
        try:
            fact["confidence"] = round(float(fact.get("confidence") or 0.0), 2)
        except (TypeError, ValueError):
            fact["confidence"] = 0.0
        facts.append(fact)
    doc["facts"] = facts
    doc["highlights"] = [
        {
            "quote": str(h.get("quote", "")),
            "file": str(h.get("file", "")),
            "reason": str(h.get("reason", "")),
        }
        for h in (data.get("highlights") or [])
        if isinstance(h, dict)
    ]
    entities = data.get("entities") or {}
    if not isinstance(entities, dict):
        entities = {}
    for key in ("topics", "organizations", "people", "technologies", "locations", "dates"):
        value = entities.get(key) or []
        doc["entities"][key] = [str(v) for v in value] if isinstance(value, list) else []
    doc["questions"] = [str(q) for q in (data.get("questions") or [])]
    doc["tags"] = [str(t) for t in (data.get("tags") or [])]
    try:
        doc["confidence"] = round(float(data.get("confidence") or 0.0), 2)
    except (TypeError, ValueError):
        doc["confidence"] = 0.0
    doc["confidence"] = min(1.0, max(0.0, doc["confidence"]))
    return doc


def build_search_text(doc: dict[str, Any]) -> str:
    entities = doc.get("entities") or {}
    parts: list[str] = [
        str(doc.get("title") or ""),
        str(doc.get("summary") or ""),
        " ".join(str(t) for t in doc.get("tags") or []),
        " ".join(str(t) for t in entities.get("topics") or []),
        " ".join(str(t) for t in entities.get("technologies") or []),
        " ".join(str(f.get("claim", "")) for f in doc.get("facts") or []),
        " ".join(str(q) for q in doc.get("questions") or []),
    ]
    return re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()


def create_job(snapshot_type: str, directory: str, template_id: Optional[int]) -> int:
    with database.db() as conn:
        cur = conn.execute(
            """
            INSERT INTO jobs (snapshot_type, directory_path, template_id, status, progress, step,
              created_at)
            VALUES (?, ?, ?, 'pending', 0, 'queued', ?)
            """,
            (snapshot_type, directory, template_id, database.now_iso()),
        )
        return int(cur.lastrowid)


def update_job(job_id: int, **fields: Any) -> None:
    if not fields:
        return
    keys = ", ".join(f"{k} = ?" for k in fields)
    with database.db() as conn:
        conn.execute(f"UPDATE jobs SET {keys} WHERE id = ?", (*fields.values(), job_id))


def get_job(job_id: int) -> Optional[dict[str, Any]]:
    with database.db() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def run_job(job_id: int, max_files: int = 200, max_chars: Optional[int] = None) -> None:
    job = get_job(job_id)
    if not job:
        return
    update_job(
        job_id,
        status="processing",
        started_at=database.now_iso(),
        step="checking_directory",
        progress=5,
    )
    try:
        snapshot_id = _run_pipeline(job_id, job, max_files, max_chars)
        update_job(
            job_id,
            status="success",
            step="done",
            progress=100,
            snapshot_id=snapshot_id,
            finished_at=database.now_iso(),
        )
    except llm_provider.ProviderError as exc:
        _fail(job_id, exc.message, exc.detail)
    except GenerationError as exc:
        _fail(job_id, exc.message, exc.detail)
    except Exception as exc:  # pragma: no cover - safety net
        _fail(job_id, "Internal error", f"{exc}\n{traceback.format_exc()[-800:]}")


def _fail(job_id: int, message: str, detail: str) -> None:
    update_job(
        job_id,
        status="failed",
        error=f"{message}: {detail}" if detail and detail != message else detail or message,
        finished_at=database.now_iso(),
    )


def _run_pipeline(
    job_id: int, job: dict[str, Any], max_files: int, max_chars: Optional[int]
) -> str:
    snapshot_type = job["snapshot_type"]
    directory = str(job["directory_path"]).strip().strip('"')
    settings = settings_service.get_settings()

    norm_dir = normalize_directory(str(Path(directory).resolve()))
    if not Path(directory).exists():
        raise GenerationError(
            "Directory not found", "Указанная директория не существует или недоступна"
        )
    if not Path(directory).is_dir():
        raise GenerationError("Not a directory", "Указанный путь не является директорией")

    template = template_service.get_template(job["template_id"]) if job["template_id"] else None
    if template is None:
        template = template_service.get_active_template(snapshot_type)
    if template is None or not template.enabled:
        raise GenerationError(
            "No active template",
            f"Для типа {snapshot_type} нет активного шаблона. "
            "Создайте или включите шаблон на странице Шаблоны.",
        )

    update_job(job_id, step="collecting_files", progress=15)
    max_input_chars = max_chars or settings.max_input_chars
    files = text_extractor.collect_files(directory, max_files)
    if not files:
        raise GenerationError(
            "No files", "В директории не найдено файлов, которые можно прочитать"
        )

    update_job(job_id, step="extracting_text", progress=30)
    docs = text_extractor.extract_documents(directory, max_files)
    if not docs:
        raise GenerationError(
            "No text", "Не удалось извлечь текст из файлов директории"
        )
    corpus = text_extractor.build_corpus(docs)
    original_chars = len(corpus)
    content_truncated = original_chars > max_input_chars
    if content_truncated:
        corpus_for_prompt = corpus[:max_input_chars]
    else:
        corpus_for_prompt = corpus

    update_job(job_id, step="generating", progress=45)
    schema_pretty = template.schema_json or json.dumps(SNAPSHOT_SCHEMA, ensure_ascii=False)
    mapping = {
        "type": snapshot_type,
        "directory": norm_dir,
        "files": ", ".join(d.file for d in docs[:50]),
        "text": corpus_for_prompt,
        "schema": schema_pretty,
        "chunk_index": 1,
        "chunk_count": 1,
        "partials": "",
    }
    chunks = chunk_text(corpus_for_prompt, settings.max_chunk_chars)
    if len(chunks) <= 1:
        user_prompt = render_prompt(template.user_prompt, mapping)
        raw = _call_llm(template.system_prompt, user_prompt, settings)
        parsed = _parse_with_retry(raw, template.system_prompt, user_prompt, settings)
    else:
        partials = []
        for idx, chunk in enumerate(chunks, start=1):
            update_job(
                job_id,
                step="generating",
                progress=int(45 + 25 * (idx - 1) / max(1, len(chunks))),
            )
            chunk_mapping = {
                **mapping,
                "text": chunk,
                "chunk_index": idx,
                "chunk_count": len(chunks),
            }
            chunk_prompt = render_prompt(
                template.chunk_user_prompt or template.user_prompt, chunk_mapping
            )
            raw = _call_llm(template.system_prompt, chunk_prompt, settings)
            try:
                partial = _parse_with_retry(
                    raw, template.system_prompt, chunk_prompt, settings
                )
            except (JsonParseError, GenerationError):
                continue
            partials.append(partial)
        if not partials:
            raise GenerationError(
                "Invalid JSON", "Модель вернула невалидный JSON для всех фрагментов"
            )
        merge_mapping = {
            **mapping,
            "partials": json.dumps(partials, ensure_ascii=False, indent=2),
        }
        merge_prompt = render_prompt(
            template.merge_user_prompt or template.user_prompt, merge_mapping
        )
        raw = _call_llm(template.system_prompt, merge_prompt, settings)
        parsed = _parse_with_retry(raw, template.system_prompt, merge_prompt, settings)

    update_job(job_id, step="parsing_json", progress=75)
    doc = normalize_snapshot_doc(parsed)

    update_job(job_id, step="verifying_quotes", progress=85)
    doc = verify_quotes(doc, corpus)

    update_job(job_id, step="saving", progress=95)
    doc["search_text"] = build_search_text(doc)
    snapshot_id = make_snapshot_id(norm_dir, snapshot_type)
    full_doc = {
        "id": snapshot_id,
        "directory": norm_dir,
        "title": doc["title"],
        "type": snapshot_type,
        "fetched_at": database.now_iso(),
        "summary": doc["summary"],
        "sections": doc["sections"],
        "facts": doc["facts"],
        "highlights": doc["highlights"],
        "entities": doc["entities"],
        "questions": doc["questions"],
        "tags": doc["tags"],
        "confidence": doc["confidence"],
        "provider": settings.provider,
        "model": settings.model,
        "template_id": template.id,
        "template_name": template.name,
        "content_hash": "sha256:" + hashlib.sha256(corpus.encode("utf-8")).hexdigest(),
        "original_chars": original_chars,
        "snapshot_chars": len(json.dumps(doc, ensure_ascii=False)),
        "file_count": len(docs),
        "files": [d.file for d in docs],
        "content_truncated": content_truncated,
        "search_text": doc["search_text"],
    }
    _save_snapshot(full_doc, norm_dir, snapshot_type, template)
    return snapshot_id


def _call_llm(system_prompt: str, user_prompt: str, settings: Any) -> str:
    if not settings.model:
        raise GenerationError("Model not configured", "Укажите модель в настройках")
    return llm_provider.chat(system_prompt, user_prompt, settings)


def _parse_with_retry(
    raw: str,
    system_prompt: str,
    user_prompt: str,
    settings: Any,
) -> dict[str, Any]:
    last_error: Optional[Exception] = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            return parse_json_response(raw)
        except JsonParseError as exc:
            last_error = exc
            if attempt == MAX_ATTEMPTS - 1:
                break
            strict = STRICT_JSON_PREFIX + user_prompt
            try:
                raw = _call_llm(system_prompt, strict, settings)
            except llm_provider.ProviderError as exc:
                last_error = exc
                break
    raise GenerationError("Invalid JSON", str(last_error or "Модель вернула невалидный JSON"))


def _save_snapshot(
    doc: dict[str, Any],
    norm_dir: str,
    snapshot_type: str,
    template: Any,
) -> str:
    snapshot_id = doc["id"]
    ts = database.now_iso()
    config.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.SNAPSHOTS_DIR / f"{snapshot_id}.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    facts = doc["facts"]
    facts_text = " ".join(
        f"{f.get('claim', '')} {f.get('quote', '')}" for f in facts
    )
    with database.db() as conn:
        previous = conn.execute(
            "SELECT created_at FROM snapshots WHERE snapshot_id = ?", (snapshot_id,)
        ).fetchone()
        created_at = previous["created_at"] if previous else ts
        conn.execute("DELETE FROM snapshots WHERE snapshot_id = ?", (snapshot_id,))
        conn.execute(
            """
            INSERT INTO snapshots (
              snapshot_id, directory_path, normalized_directory, snapshot_type, template_id,
              template_name, provider, model, status, error, title, summary, sections_json,
              facts_json, highlights_json, entities_json, questions_json, tags_json, confidence,
              content_hash, original_chars, snapshot_chars, file_count, files_json,
              content_truncated, search_text, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'success', NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
              ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                doc["directory"],
                norm_dir,
                snapshot_type,
                template.id,
                template.name,
                doc["provider"],
                doc["model"],
                doc["title"],
                doc["summary"],
                json.dumps(doc["sections"], ensure_ascii=False),
                json.dumps(doc["facts"], ensure_ascii=False),
                json.dumps(doc["highlights"], ensure_ascii=False),
                json.dumps(doc["entities"], ensure_ascii=False),
                json.dumps(doc["questions"], ensure_ascii=False),
                json.dumps(doc["tags"], ensure_ascii=False),
                doc["confidence"],
                doc["content_hash"],
                doc["original_chars"],
                doc["snapshot_chars"],
                doc["file_count"],
                json.dumps(doc["files"], ensure_ascii=False),
                1 if doc["content_truncated"] else 0,
                doc["search_text"],
                created_at,
                ts,
            ),
        )
        _index_fts(
            conn,
            snapshot_id=snapshot_id,
            title=doc["title"] or "",
            directory=norm_dir,
            search_text=doc["search_text"],
            summary=doc["summary"] or "",
            facts_text=facts_text,
            tags_text=" ".join(doc["tags"]),
            questions_text=" ".join(doc["questions"]),
        )
    return snapshot_id


def _index_fts(conn: Any, **fields: Any) -> None:
    if not database.fts_available(conn):
        return
    conn.execute("DELETE FROM snapshots_fts WHERE snapshot_id = ?", (fields["snapshot_id"],))
    conn.execute(
        """
        INSERT INTO snapshots_fts (snapshot_id, title, directory, search_text, summary,
          facts_text, tags_text, questions_text)
        VALUES (:snapshot_id, :title, :directory, :search_text, :summary, :facts_text,
          :tags_text, :questions_text)
        """,
        fields,
    )
