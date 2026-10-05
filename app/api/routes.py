from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from .. import config, database, i18n
from ..models import (
    is_valid_source_url,
    normalize_source_url,
    snapshot_type_label,
    step_label,
)
from ..schemas import (
    HealthOut,
    JobOut,
    ProviderTestIn,
    ProviderTestOut,
    SettingsOut,
    SettingsUpdate,
    SnapshotCreate,
    SnapshotFromUrl,
    SnapshotListOut,
    SourceUrlUpdate,
    TemplateIn,
    TemplateOut,
    TemplateTestIn,
    TemplateTestOut,
)
from ..services import (
    llm_provider,
    settings_service,
    snapshot_generator,
    snapshot_search,
    snapshot_sender,
    template_service,
    text_extractor,
)

api = APIRouter(prefix="/api")
pages = APIRouter()


def _error(status: int, code: str, detail: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": code, "detail": detail})


# ---------------------------------------------------------------- health
@api.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    settings = settings_service.get_settings()
    test = llm_provider.test_connection(
        settings.provider, settings.base_url, settings.api_key, settings.model
    )
    stats = snapshot_search.stats()
    return HealthOut(
        status="ok",
        provider=settings.provider,
        model=settings.model,
        provider_reachable=test.reachable,
        model_available=test.model_available,
        snapshot_count=stats["total"],
        template_count=stats["template_count"],
    )


@api.get("/stats")
def stats_endpoint() -> dict:
    return snapshot_search.stats()


# ---------------------------------------------------------------- settings
@api.get("/settings", response_model=SettingsOut)
def get_settings() -> SettingsOut:
    return settings_service.get_settings()


@api.put("/settings", response_model=SettingsOut)
def put_settings(payload: SettingsUpdate) -> SettingsOut:
    if payload.provider not in config.PROVIDERS:
        raise _error(400, "Invalid provider", i18n.t("Провайдер должен быть одним из: ") + ", ".join(config.PROVIDERS))
    if payload.language not in i18n.LANGUAGES:
        raise _error(400, "Invalid language", i18n.t("Язык должен быть одним из: en, pl, ru"))
    if payload.temperature < 0 or payload.temperature > 2:
        raise _error(400, "Invalid temperature", i18n.t("temperature должен быть в диапазоне 0.0–2.0"))
    if payload.max_input_chars < 500:
        raise _error(400, "Invalid max_input_chars", i18n.t("max_input_chars должен быть не меньше 500"))
    if payload.max_chunk_chars < 200:
        raise _error(400, "Invalid max_chunk_chars", i18n.t("max_chunk_chars должен быть не меньше 200"))
    return settings_service.update_settings(payload)


@api.post("/providers/test", response_model=ProviderTestOut)
def provider_test(payload: ProviderTestIn) -> ProviderTestOut:
    return llm_provider.test_connection(
        payload.provider, payload.base_url, payload.api_key, payload.model
    )


# ---------------------------------------------------------------- templates
@api.get("/templates", response_model=list[TemplateOut])
def list_templates(
    snapshot_type: Optional[str] = Query(None), enabled: Optional[bool] = Query(None)
) -> list[TemplateOut]:
    return template_service.list_templates(snapshot_type, enabled)


@api.post("/templates", response_model=TemplateOut)
def create_template(payload: TemplateIn) -> TemplateOut:
    try:
        return template_service.create_template(payload)
    except template_service.TemplateError as exc:
        raise _error(400, "Invalid template", str(exc))


@api.get("/templates/{template_id}", response_model=TemplateOut)
def get_template(template_id: int) -> TemplateOut:
    template = template_service.get_template(template_id)
    if not template:
        raise _error(404, "Template not found", i18n.t("Шаблон {id} не найден", id=template_id))
    return template


@api.put("/templates/{template_id}", response_model=TemplateOut)
def update_template(template_id: int, payload: TemplateIn) -> TemplateOut:
    try:
        template = template_service.update_template(template_id, payload)
    except template_service.TemplateError as exc:
        raise _error(400, "Invalid template", str(exc))
    if not template:
        raise _error(404, "Template not found", i18n.t("Шаблон {id} не найден", id=template_id))
    return template


@api.delete("/templates/{template_id}")
def delete_template(template_id: int) -> dict:
    template = template_service.get_template(template_id)
    if not template:
        raise _error(404, "Template not found", i18n.t("Шаблон {id} не найден", id=template_id))
    warnings = template_service.usage_warnings(template)
    template_service.delete_template(template_id)
    return {"deleted": True, "warnings": warnings}


@api.post("/templates/{template_id}/default")
def set_default_template(template_id: int) -> dict:
    try:
        template = template_service.set_default(template_id)
    except template_service.TemplateError as exc:
        raise _error(400, "Invalid template", str(exc))
    return {"ok": True, "template": template}


@api.post("/templates/{template_id}/enabled")
def toggle_template(template_id: int, enabled: bool = Query(True)) -> TemplateOut:
    template = template_service.toggle_enabled(template_id, enabled)
    if not template:
        raise _error(404, "Template not found", i18n.t("Шаблон {id} не найден", id=template_id))
    return template


@api.post("/templates/{template_id}/test", response_model=TemplateTestOut)
def test_template(template_id: int, payload: TemplateTestIn) -> TemplateTestOut:
    template = template_service.get_template(template_id)
    if not template:
        raise _error(404, "Template not found", i18n.t("Шаблон {id} не найден", id=template_id))
    settings = settings_service.get_settings()
    sample = payload.sample_text.strip() or "Ollama позволяет запускать локальные LLM локально."
    schema_pretty = template.template_schema or "{}"
    mapping = {
        "type": payload.type or template.snapshot_type,
        "directory": payload.directory,
        "files": "sample.txt",
        "text": sample,
        "schema": schema_pretty,
        "chunk_index": 1,
        "chunk_count": 1,
        "partials": "",
    }
    user_prompt = snapshot_generator.render_prompt(template.user_prompt, mapping)
    try:
        raw = llm_provider.chat(template.system_prompt, user_prompt, settings)
    except llm_provider.ProviderError as exc:
        return TemplateTestOut(success=False, raw_output="", parsed_json=None, error=exc.detail)
    try:
        parsed = snapshot_generator.parse_snapshot_response(raw)
    except snapshot_generator.JsonParseError as exc:
        return TemplateTestOut(success=False, raw_output=raw, parsed_json=None, error=str(exc))
    return TemplateTestOut(success=True, raw_output=raw, parsed_json=parsed, error=None)


# ---------------------------------------------------------------- snapshots
@api.post("/snapshots")
def create_snapshot(
    payload: SnapshotCreate, background_tasks: BackgroundTasks
) -> dict:
    if payload.snapshot_type not in config.SNAPSHOT_TYPES:
        raise _error(
            400,
            "Invalid type",
            i18n.t(
                "Недопустимый тип слепка. Допустимые: {types}",
                types=", ".join(config.SNAPSHOT_TYPES),
            ),
        )
    directory = (payload.directory or "").strip().strip('"')
    if not directory:
        raise _error(400, "Directory required", i18n.t("Укажите директорию"))
    source_url = (payload.source_url or "").strip()
    if not source_url:
        raise _error(400, "Source URL required", i18n.t("Укажите source_url — ссылку на сайт/репозиторий"))
    if not is_valid_source_url(source_url):
        raise _error(400, "Invalid source URL", i18n.t("source_url должен быть http(s)-ссылкой"))
    source_url = normalize_source_url(source_url)
    path = Path(directory)
    if not path.exists():
        raise _error(400, "Directory not found", i18n.t("Указанная директория не существует или недоступна"))
    if not path.is_dir():
        raise _error(400, "Not a directory", i18n.t("Указанный путь не является директорией"))
    template = template_service.get_active_template(payload.snapshot_type)
    if template is None:
        raise _error(
            409,
            "No active template",
            i18n.t(
                "Для типа {type} нет активного шаблона. "
                "Создайте или включите шаблон на странице Шаблоны.",
                type=payload.snapshot_type,
            ),
        )
    job_id = snapshot_generator.create_job(
        payload.snapshot_type, str(path), template.id, source_url
    )
    snapshot_id = snapshot_generator.make_snapshot_id(
        snapshot_generator.normalize_directory(str(path.resolve())), payload.snapshot_type
    )
    background_tasks.add_task(
        snapshot_generator.run_job,
        job_id,
        payload.max_files,
        payload.max_chars,
    )
    return {"job_id": job_id, "snapshot_id": snapshot_id}


@api.post("/snapshots/from-url")
def create_snapshot_from_url(
    payload: SnapshotFromUrl, background_tasks: BackgroundTasks
) -> dict:
    if payload.snapshot_type not in config.SNAPSHOT_TYPES:
        raise _error(
            400,
            "Invalid type",
            i18n.t(
                "Недопустимый тип слепка. Допустимые: {types}",
                types=", ".join(config.SNAPSHOT_TYPES),
            ),
        )
    url = normalize_source_url((payload.url or "").strip())
    if not is_valid_source_url(url):
        raise _error(400, "Invalid URL", i18n.t("Укажите корректную http(s)-ссылку на страницу"))
    template = template_service.get_active_template(payload.snapshot_type)
    if template is None:
        raise _error(
            409,
            "No active template",
            i18n.t(
                "Для типа {type} нет активного шаблона. "
                "Создайте или включите шаблон на странице Шаблоны.",
                type=payload.snapshot_type,
            ),
        )
    job_id = snapshot_generator.create_job(payload.snapshot_type, url, template.id, url)
    snapshot_id = snapshot_generator.make_snapshot_id(url, payload.snapshot_type)
    background_tasks.add_task(
        snapshot_generator.run_job,
        job_id,
        200,
        payload.max_chars,
    )
    return {"job_id": job_id, "snapshot_id": snapshot_id}


@api.get("/snapshots/exists")
def snapshot_exists(directory: str = Query(...), snapshot_type: str = Query(...)) -> dict:
    snapshot_id = snapshot_search.exists_for_directory(directory, snapshot_type)
    return {"exists": bool(snapshot_id), "snapshot_id": snapshot_id}


@api.get("/snapshots", response_model=SnapshotListOut)
def list_snapshots(
    query: str = "",
    type: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    template_id: Optional[int] = Query(None),
    min_confidence: Optional[float] = Query(None),
    max_age_days: Optional[int] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> SnapshotListOut:
    result = snapshot_search.search_snapshots(
        query=query,
        type_=type,
        provider=provider,
        model=model,
        template_id=template_id,
        min_confidence=min_confidence,
        max_age_days=max_age_days,
        limit=limit,
        offset=offset,
    )
    return SnapshotListOut(**result)


@api.patch("/snapshots/{snapshot_id}/source_url")
def patch_source_url(snapshot_id: str, payload: SourceUrlUpdate) -> dict:
    try:
        norm = snapshot_generator.update_source_url(snapshot_id, payload.source_url)
    except snapshot_generator.GenerationError as exc:
        status = 404 if exc.message == "Snapshot not found" else 400
        raise _error(status, exc.message, exc.detail)
    return {"updated": True, "source_url": norm}


@api.get("/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: str) -> dict:
    data = snapshot_search.get_snapshot(snapshot_id)
    if not data:
        raise _error(404, "Snapshot not found", i18n.t("Слепок {id} не найден", id=snapshot_id))
    data["sections"] = json.loads(data.pop("sections_json") or "[]")
    data["facts"] = json.loads(data.pop("facts_json") or "[]")
    data["highlights"] = json.loads(data.pop("highlights_json") or "[]")
    data["entities"] = json.loads(data.pop("entities_json") or "{}")
    data["questions"] = json.loads(data.pop("questions_json") or "[]")
    data["tags"] = json.loads(data.pop("tags_json") or "[]")
    data["files"] = json.loads(data.pop("files_json") or "[]")
    data["type_label"] = snapshot_type_label(data.get("snapshot_type", ""))
    return data


@api.get("/snapshots/{snapshot_id}/raw")
def raw_snapshot(snapshot_id: str) -> Response:
    data = snapshot_search.read_raw(snapshot_id)
    if data is None:
        raise _error(404, "Snapshot not found", i18n.t("JSON-файл слепка {id} не найден", id=snapshot_id))
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="{snapshot_id}.json"'},
    )


@api.post("/snapshots/{snapshot_id}/send")
def send_snapshot(snapshot_id: str) -> dict:
    result = snapshot_sender.send_snapshot(snapshot_id)
    if not result.ok:
        raise _error(502, "Send failed", result.error or "Не удалось отправить слепок")
    return {"sent": True, "status_code": result.status_code}


@api.delete("/snapshots/{snapshot_id}")
def delete_snapshot(snapshot_id: str) -> dict:
    if not snapshot_search.delete_snapshot(snapshot_id):
        raise _error(404, "Snapshot not found", i18n.t("Слепок {id} не найден", id=snapshot_id))
    return {"deleted": True}


# ---------------------------------------------------------------- jobs
@api.get("/jobs/{job_id}")
def get_job(job_id: int) -> JobOut:
    job = snapshot_generator.get_job(job_id)
    if not job:
        raise _error(404, "Job not found", i18n.t("Задача {id} не найдена", id=job_id))
    return JobOut(
        id=job["id"],
        snapshot_type=job["snapshot_type"],
        directory_path=job["directory_path"],
        template_id=job["template_id"],
        status=job["status"],
        progress=job["progress"],
        step=job["step"],
        step_label=step_label(job["step"]),
        error=job["error"],
        snapshot_id=job["snapshot_id"],
        created_at=job["created_at"],
        started_at=job["started_at"],
        finished_at=job["finished_at"],
    )


# ---------------------------------------------------------------- auxiliary
@api.get("/models")
def list_models() -> dict:
    settings = settings_service.get_settings()
    try:
        models = llm_provider.list_models(
            settings.provider, settings.base_url, settings.api_key
        )
    except llm_provider.ProviderError as exc:
        raise _error(502, exc.message, exc.detail)
    return {"models": models}


@api.get("/meta")
def meta() -> dict:
    settings = settings_service.get_settings()
    provider_models: list[str] = []
    try:
        provider_models = llm_provider.list_models(
            settings.provider, settings.base_url, settings.api_key, timeout=3
        )
    except llm_provider.ProviderError:
        provider_models = []
    models = sorted(set(provider_models) | set(snapshot_search.distinct_models()))
    return {
        "models": models,
        "templates": [t.model_dump(by_alias=True) for t in template_service.list_templates()],
        "types": config.SNAPSHOT_TYPES,
    }


@api.get("/files")
def preview_files(directory: str = Query(...), max_files: int = 50) -> dict:
    path = Path(directory)
    if not path.exists() or not path.is_dir():
        raise _error(400, "Directory not found", i18n.t("Указанная директория не существует"))
    files = [str(f.relative_to(path)).replace("\\", "/") for f in text_extractor.collect_files(directory, max_files)]
    return {"count": len(files), "files": files}


# ---------------------------------------------------------------- pages
@pages.get("/")
def index(request: Request):
    return _render(request, "index.html")


@pages.get("/create")
def create_page(request: Request):
    return _render(request, "create.html")


@pages.get("/templates")
def templates_page(request: Request):
    return _render(request, "templates.html")


@pages.get("/search")
def search_page(request: Request):
    return _render(request, "search.html")


@pages.get("/settings")
def settings_page(request: Request):
    return _render(request, "settings.html")


@pages.get("/snapshots/{snapshot_id}")
def snapshot_page(request: Request, snapshot_id: str):
    if not snapshot_search.get_snapshot(snapshot_id):
        raise _error(404, "Snapshot not found", i18n.t("Слепок {id} не найден", id=snapshot_id))
    return _render(request, "snapshot_detail.html", {"snapshot_id": snapshot_id})


def _render(request: Request, name: str, context: Optional[dict] = None):
    lang = i18n.get_language()
    ctx: dict = {
        "request": request,
        "lang": lang,
        "t_dict": i18n.as_dict(lang),
    }
    ctx.update(context or {})
    template = request.app.state.templates.get_template(name)
    return HTMLResponse(template.render(ctx))
