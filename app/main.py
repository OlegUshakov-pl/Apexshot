from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import config, database, i18n, search
from .api.routes import api, pages
from .api.search import api as search_api

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    from .services import settings_service

    settings_service.sync_language()
    database.reset_stale_jobs(i18n.t("Задача прервана перезапуском сервера"))
    # Гибридный индекс: ChromaDB + BM25 из локальных JSON-слепков.
    # Если Ollama поднята — докачка/проверка модели bge-m3; иначе поиск
    # деградирует до BM25-only (WARNING, приложение не падает).
    try:
        from .search.ollama_client import get_client

        get_client().ensure_model()
    except Exception as exc:  # noqa: BLE001 — старт не должен ломаться
        import logging

        logging.getLogger("search.ollama").warning(
            "Ollama недоступна при старте: %s — поиск деградирует до BM25-only", exc
        )
    search.rebuild_search_index()
    yield


app = FastAPI(title="AI-snapshot", version="1.0.0", lifespan=lifespan)

# CORS только для Chrome-расширений (origin вида chrome-extension://<id>),
# чтобы расширение могло звать POST /api/search.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"chrome-extension://.*",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.state.templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.state.templates.env.globals["t"] = i18n.t
app.state.templates.env.globals["languages"] = i18n.LANGUAGES

app.include_router(api)
app.include_router(search_api)
app.include_router(pages)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        payload = {"error": detail.get("error", "Error"), "detail": detail.get("detail", "")}
    else:
        payload = {"error": "Error", "detail": str(detail)}
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal error", "detail": f"{type(exc).__name__}: {exc}"},
    )


def create_app() -> FastAPI:
    return app
