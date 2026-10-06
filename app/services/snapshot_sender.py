from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import httpx

from ..models import is_local_url
from . import settings_service
from .snapshot_search import get_snapshot, read_raw


@dataclass
class SendResult:
    ok: bool
    status_code: Optional[int] = None
    error: str = ""


@dataclass
class ServerTestResult:
    reachable: bool = False
    status_code: Optional[int] = None
    error: str = ""


def test_server(server_url: str, timeout: float = 10.0) -> ServerTestResult:
    url = (server_url or "").strip()
    if not url:
        return ServerTestResult(error="Server URL не задан")
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
    except httpx.HTTPError as exc:
        return ServerTestResult(error=f"Нет соединения: {exc}")
    # Любой HTTP-ответ (даже 404/405 — адрес ведь для POST) означает, что сервер жив.
    return ServerTestResult(reachable=True, status_code=resp.status_code)


def send_snapshot(snapshot_id: str, server_url: Optional[str] = None, timeout: float = 30.0) -> SendResult:
    url = (server_url or "").strip() or settings_service.get_settings().server_url.strip()
    if not url:
        return SendResult(ok=False, error="Server URL не задан. Укажите его на странице Settings.")
    data: Optional[dict[str, Any]] = read_raw(snapshot_id)
    if data is None:
        return SendResult(ok=False, error=f"JSON-файл слепка {snapshot_id} не найден")
    source_url = str(data.get("source_url") or "").strip()
    if not source_url:
        row = get_snapshot(snapshot_id)
        if row:
            source_url = str(row.get("source_url") or "").strip()
    if not source_url:
        return SendResult(
            ok=False,
            error="У слепка нет source_url — отправка запрещена. Пересоздайте слепок с ссылкой на сайт.",
        )
    if is_local_url(source_url):
        return SendResult(
            ok=False,
            error=f"source_url {source_url} — локальный адрес, отправка на сервер запрещена.",
        )
    try:
        resp = httpx.post(url, json=data, timeout=timeout)
    except httpx.HTTPError as exc:
        return SendResult(ok=False, error=f"Ошибка соединения: {exc}")
    if 200 <= resp.status_code < 300:
        return SendResult(ok=True, status_code=resp.status_code)
    body = (resp.text or "")[:500]
    return SendResult(ok=False, status_code=resp.status_code, error=f"Сервер вернул {resp.status_code}: {body}")
