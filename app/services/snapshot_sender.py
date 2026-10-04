from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import httpx

from . import settings_service
from .snapshot_search import read_raw


@dataclass
class SendResult:
    ok: bool
    status_code: Optional[int] = None
    error: str = ""


def send_snapshot(snapshot_id: str, server_url: Optional[str] = None, timeout: float = 30.0) -> SendResult:
    url = (server_url or "").strip() or settings_service.get_settings().server_url.strip()
    if not url:
        return SendResult(ok=False, error="Server URL не задан. Укажите его на странице Settings.")
    data: Optional[dict[str, Any]] = read_raw(snapshot_id)
    if data is None:
        return SendResult(ok=False, error=f"JSON-файл слепка {snapshot_id} не найден")
    try:
        resp = httpx.post(url, json=data, timeout=timeout)
    except httpx.HTTPError as exc:
        return SendResult(ok=False, error=f"Ошибка соединения: {exc}")
    if 200 <= resp.status_code < 300:
        return SendResult(ok=True, status_code=resp.status_code)
    body = (resp.text or "")[:500]
    return SendResult(ok=False, status_code=resp.status_code, error=f"Сервер вернул {resp.status_code}: {body}")
