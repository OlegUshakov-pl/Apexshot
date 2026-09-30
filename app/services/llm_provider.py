from __future__ import annotations

from typing import Any, Optional

import httpx

from .. import config
from ..schemas import ProviderTestOut, SettingsOut


class ProviderError(Exception):
    def __init__(self, message: str, detail: str = ""):
        super().__init__(detail or message)
        self.message = message
        self.detail = detail or message


def normalize_base_url(provider: str, base_url: str) -> str:
    url = (base_url or "").strip().rstrip("/")
    if not url:
        url = config.DEFAULT_BASE_URLS.get(provider, "")
    if provider == "lmstudio":
        if url.endswith("/v1"):
            pass
        elif "/v1/" in url:
            url = url.split("/v1/")[0] + "/v1"
        else:
            url = url + "/v1"
    return url


def list_models(provider: str, base_url: str, api_key: str = "", timeout: int = 15) -> list[str]:
    url = normalize_base_url(provider, base_url)
    headers = _headers(api_key)
    try:
        if provider == "ollama":
            with httpx.Client(timeout=timeout, headers=headers) as client:
                resp = client.get(f"{url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        with httpx.Client(timeout=timeout, headers=headers) as client:
            resp = client.get(f"{url}/models")
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", data if isinstance(data, list) else [])
        return [m.get("id", "") for m in items if isinstance(m, dict) and m.get("id")]
    except httpx.HTTPError as exc:
        raise ProviderError("Provider unreachable", f"Не удалось подключиться к {url}: {exc}") from exc
    except ValueError as exc:
        raise ProviderError("Invalid response", f"Провайдер вернул некорректный ответ: {exc}") from exc


def test_connection(
    provider: str, base_url: str, api_key: str = "", model: str = ""
) -> ProviderTestOut:
    provider = provider if provider in config.PROVIDERS else "ollama"
    url = normalize_base_url(provider, base_url)
    try:
        models = list_models(provider, base_url, api_key)
    except ProviderError as exc:
        return ProviderTestOut(reachable=False, model_available=False, models=[], error=exc.detail)
    model_available = bool(model) and model in models
    if model and not models:
        model_available = True
    return ProviderTestOut(
        reachable=True, model_available=model_available, models=models, error=None
    )


def chat(
    system_prompt: str,
    user_prompt: str,
    settings: SettingsOut,
    json_mode: Optional[bool] = None,
) -> str:
    provider = settings.provider if settings.provider in config.PROVIDERS else "ollama"
    url = normalize_base_url(provider, settings.base_url)
    use_json = settings.json_mode if json_mode is None else json_mode
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    timeout = settings.timeout_seconds or 300
    try:
        if provider == "ollama":
            payload: dict[str, Any] = {
                "model": settings.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": settings.temperature,
                    "top_p": settings.top_p,
                    "seed": settings.seed,
                    "num_predict": settings.max_tokens,
                },
            }
            if use_json:
                payload["format"] = "json"
            with httpx.Client(timeout=timeout, headers=_headers(settings.api_key)) as client:
                resp = client.post(f"{url}/api/chat", json=payload)
            if resp.status_code >= 400:
                raise ProviderError(
                    "Provider error", f"Ошибка Ollama ({resp.status_code}): {resp.text[:300]}"
                )
            data = resp.json()
            return (data.get("message") or {}).get("content", "") or ""

        payload = {
            "model": settings.model,
            "messages": messages,
            "temperature": settings.temperature,
            "top_p": settings.top_p,
            "seed": settings.seed,
            "max_tokens": settings.max_tokens,
            "stream": False,
        }
        if use_json:
            payload["response_format"] = {"type": "json_object"}
        with httpx.Client(timeout=timeout, headers=_headers(settings.api_key)) as client:
            resp = client.post(f"{url}/chat/completions", json=payload)
            if resp.status_code >= 400 and use_json and "response_format" in resp.text:
                payload.pop("response_format", None)
                resp = client.post(f"{url}/chat/completions", json=payload)
        if resp.status_code >= 400:
            raise ProviderError(
                "Provider error", f"Ошибка LM Studio ({resp.status_code}): {resp.text[:300]}"
            )
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            return ""
        return (choices[0].get("message") or {}).get("content", "") or ""
    except ProviderError:
        raise
    except httpx.TimeoutException as exc:
        raise ProviderError(
            "Provider timeout", f"Превышено время ожидания ответа от {url} ({timeout} c)"
        ) from exc
    except httpx.HTTPError as exc:
        raise ProviderError(
            "Provider unreachable", f"Не удалось подключиться к {provider} на {url}: {exc}"
        ) from exc
    except ValueError as exc:
        raise ProviderError("Invalid response", f"Провайдер вернул некорректный JSON: {exc}") from exc


def _headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers
