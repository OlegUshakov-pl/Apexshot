from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

from .. import config, i18n
from ..schemas import ProviderTestOut, SettingsOut

logger = logging.getLogger("provider")

# --- Автоподбор модели на текущей машине -------------------------------------
# Настройки (в т.ч. model) общие для всех машин, а модели в локальной Ollama /
# LM Studio на каждой машине свои. Если сконфигурированной модели нет — берём:
# 1) модель того же семейства ("gemma4:e4b" -> "gemma4:12b");
# 2) любую установленную не-эмбеддинговую модель.
# Таблица подмены кэшируется на короткое время, чтобы не звать /api/tags
# на каждый чат-вызов, но и не «залипать» на старую раскладку навсегда.

_FALLBACK_TTL = 60.0
_model_fallback_cache: dict[tuple[str, str, str], tuple[float, str]] = {}

_EMBED_MODEL_HINTS = ("bge", "embed", "minilm", "gte-", "e5-", "jina")


def _family(name: str) -> str:
    """Семейство модели: 'tobestyledintro/qwen:q6' -> 'qwen', 'gemma4:e4b' -> 'gemma4'."""
    return (name or "").split(":")[0].rsplit("/", 1)[-1].lower()


def _is_embedding_model(name: str) -> bool:
    low = (name or "").lower()
    return any(hint in low for hint in _EMBED_MODEL_HINTS)


def _pick_installed(installed: list[str], model: str) -> str:
    if model in installed:
        return model
    family = _family(model)
    for candidate in installed:
        if _family(candidate) == family:
            return candidate
    for candidate in installed:
        if not _is_embedding_model(candidate):
            return candidate
    return model


def resolve_local_model(
    provider: str, base_url: str, api_key: str = "", model: str = "", timeout: int = 5
) -> str:
    """Возвращает модель, реально установленную на этой машине (для локальных провайдеров).

    Никогда не бросает исключений: при любой проблеме возвращается исходное имя.
    """
    if provider not in ("ollama", "lmstudio") or not model:
        return model
    key = (provider, base_url or "", model)
    cached = _model_fallback_cache.get(key)
    now = time.monotonic()
    if cached and now - cached[0] < _FALLBACK_TTL:
        return cached[1]
    try:
        installed = list_models(provider, base_url, api_key, timeout=timeout)
    except ProviderError:
        # провайдер недоступен — пусть обычная обработка ошибок покажет это
        return model
    except Exception:  # noqa: BLE001 — мок-объекты в тестах могут не иметь .get
        return model
    resolved = _pick_installed(installed, model)
    _model_fallback_cache[key] = (now, resolved)
    if resolved != model:
        logger.warning(
            "Модель '%s' не установлена на этой машине — используется '%s' "
            "(настройка не менялась, подмена только на текущей машине)",
            model,
            resolved,
        )
    return resolved


def clear_model_fallback_cache() -> None:
    _model_fallback_cache.clear()


class ProviderError(Exception):
    def __init__(self, message: str, detail: str = ""):
        super().__init__(detail or message)
        self.message = message
        self.detail = detail or message


def normalize_base_url(provider: str, base_url: str) -> str:
    url = (base_url or "").strip().rstrip("/")
    if not url:
        url = config.DEFAULT_BASE_URLS.get(provider, "")
    if provider in ("lmstudio", "openai", "mistral", "groq", "deepseek", "openrouter", "opencode"):
        if url.endswith("/v1"):
            pass
        elif "/v1/" in url:
            url = url.split("/v1/")[0] + "/v1"
        else:
            url = url + "/v1"
    return url


def _auth_headers(provider: str, api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if not api_key:
        return headers
    if provider == "anthropic":
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    elif provider == "google":
        # key goes as query param, nothing to add here
        pass
    else:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def list_models(provider: str, base_url: str, api_key: str = "", timeout: int = 15) -> list[str]:
    url = normalize_base_url(provider, base_url)
    headers = _auth_headers(provider, api_key)
    try:
        if provider == "ollama":
            with httpx.Client(timeout=timeout, headers=headers) as client:
                resp = client.get(f"{url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        if provider == "anthropic":
            with httpx.Client(timeout=timeout, headers=headers) as client:
                resp = client.get(f"{url}/models")
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", [])
            return [m.get("id", "") for m in items if isinstance(m, dict) and m.get("id")]
        if provider == "google":
            sep = "&" if "?" in url else "?"
            with httpx.Client(timeout=timeout, headers=headers) as client:
                resp = client.get(f"{url}/models{sep}key={api_key}")
            resp.raise_for_status()
            data = resp.json()
            out = []
            for m in data.get("models", []):
                name = m.get("name", "")
                if name.startswith("models/"):
                    name = name[len("models/"):]
                if name:
                    out.append(name)
            return out
        with httpx.Client(timeout=timeout, headers=headers) as client:
            resp = client.get(f"{url}/models")
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", data if isinstance(data, list) else [])
        return [m.get("id", "") for m in items if isinstance(m, dict) and m.get("id")]
    except httpx.HTTPError as exc:
        raise ProviderError(
            "Provider unreachable",
            i18n.t("Не удалось подключиться к {url}: {error}", url=url, error=exc),
        ) from exc
    except ValueError as exc:
        raise ProviderError(
            "Invalid response",
            i18n.t("Провайдер вернул некорректный ответ: {error}", error=exc),
        ) from exc


def test_connection(
    provider: str, base_url: str, api_key: str = "", model: str = ""
) -> ProviderTestOut:
    provider = provider if provider in config.PROVIDERS else "ollama"
    url = normalize_base_url(provider, base_url)
    try:
        models = list_models(provider, base_url, api_key)
    except ProviderError as exc:
        return ProviderTestOut(reachable=False, model_available=False, models=[], error=exc.detail)
    # Модель может быть подменена авто-подбором на этой машине — тогда считаем,
    # что модель доступна (см. resolve_local_model / _pick_installed).
    model_available = bool(model) and (model in models or _pick_installed(models, model) in models)
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
    # Локальные провайдеры: подбираем реально установленную модель (см. выше),
    # чтобы настройки, общие для нескольких машин, не ломали генерацию.
    model = resolve_local_model(
        provider, settings.base_url, settings.api_key, settings.model
    )
    use_json = settings.json_mode if json_mode is None else json_mode
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    # timeout_seconds <= 0 означает «ждать бесконечно»: httpx понимает timeout=None.
    raw_timeout = settings.timeout_seconds or 0
    timeout: float | None = raw_timeout if raw_timeout > 0 else None
    headers = _auth_headers(provider, settings.api_key)
    try:
        if provider == "anthropic":
            payload: dict[str, Any] = {
                "model": settings.model,
                "max_tokens": settings.max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
                "temperature": settings.temperature,
                "top_p": settings.top_p,
            }
            with httpx.Client(timeout=timeout, headers=headers) as client:
                resp = client.post(f"{url}/messages", json=payload)
            if resp.status_code >= 400:
                raise ProviderError("Provider error", f"Ошибка Anthropic ({resp.status_code}): {resp.text[:300]}")
            data = resp.json()
            blocks = data.get("content") or []
            return "".join(b.get("text", "") for b in blocks if isinstance(b, dict)) or ""
        if provider == "google":
            sep = "&" if "?" in url else "?"
            gurl = f"{url}/models/{settings.model}:generateContent{sep}key={settings.api_key}"
            payload = {
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"parts": [{"text": user_prompt}]}],
                "generationConfig": {"temperature": settings.temperature, "topP": settings.top_p,
                                     "maxOutputTokens": settings.max_tokens},
            }
            with httpx.Client(timeout=timeout, headers=headers) as client:
                resp = client.post(gurl, json=payload)
            if resp.status_code >= 400:
                raise ProviderError("Provider error", f"Ошибка Google ({resp.status_code}): {resp.text[:300]}")
            data = resp.json()
            try:
                parts = data["candidates"][0]["content"]["parts"]
                return "".join(p.get("text", "") for p in parts) or ""
            except (KeyError, IndexError, TypeError):
                return ""
        if provider == "ollama":
            payload: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": False,
                # Reasoning-модели (deepseek-r1, qwen3 и т.п.) по умолчанию
                # думают — отключаем thinking, нужен только финальный ответ.
                # Важно: think — top-level поле, НЕ внутри options.
                "think": False,
                "options": {
                    "temperature": settings.temperature,
                    "top_p": settings.top_p,
                    "seed": settings.seed,
                    "num_predict": settings.max_tokens,
                    # Ограничиваем контекст: без этого Ollama грузит модель
                    # с дефолтным большим контекстом (напр. 64k), KV-кэш
                    # не влезает в VRAM, модель едет на CPU и всё тормозит.
                    # Вход приложения и так обрезан max_input_chars (~12k
                    # символов), так что 16384 хватает с запасом.
                    "num_ctx": 16384,
                },
            }
            if use_json:
                payload["format"] = "json"
            with httpx.Client(timeout=timeout, headers=headers) as client:
                resp = client.post(f"{url}/api/chat", json=payload)
                if resp.status_code >= 400 and use_json and "format" in resp.text.lower():
                    # Старые/мелкие модели Ollama не поддерживают format=json —
                    # повторяем без него, парсер вытащит JSON из текста.
                    payload.pop("format", None)
                    resp = client.post(f"{url}/api/chat", json=payload)
                if resp.status_code >= 400 and "think" in resp.text.lower():
                    # Модель/версия Ollama не умеет отключать thinking —
                    # повторяем без параметра (reasoning попадёт в ответ,
                    # парсер отделяет финальный JSON).
                    payload.pop("think", None)
                    resp = client.post(f"{url}/api/chat", json=payload)
            if resp.status_code >= 400:
                raise ProviderError(
                    "Provider error",
                    i18n.t(
                        "Ошибка Ollama ({status}): {body}",
                        status=resp.status_code,
                        body=resp.text[:300],
                    ),
                )
            data = resp.json()
            return (data.get("message") or {}).get("content", "") or ""

        payload = {
            "model": model,
            "messages": messages,
            "temperature": settings.temperature,
            "top_p": settings.top_p,
            "seed": settings.seed,
            "max_tokens": settings.max_tokens,
            "stream": False,
            # Отключаем thinking/reasoning для OpenAI-совместимых провайдеров
            # (LM Studio, OpenRouter, DeepSeek, Groq и т.п.):
            # reasoning_effort=none — документированный способ,
            # остальное — для qwen/прочих шаблонов, игнорируется если не поддержано.
            "reasoning_effort": "none",
            "enable_thinking": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if use_json:
            payload["response_format"] = {"type": "json_object"}
        with httpx.Client(timeout=timeout, headers=headers) as client:
            resp = client.post(f"{url}/chat/completions", json=payload)
            # Часть reasoning-моделей не позволяет отключить thinking
            # ("Reasoning is mandatory for this endpoint..." — LM Studio,
            # OpenRouter) — повторяем без параметров отключения reasoning.
            if resp.status_code >= 400 and "reasoning" in resp.text.lower():
                for key in ("reasoning_effort", "enable_thinking", "chat_template_kwargs"):
                    payload.pop(key, None)
                resp = client.post(f"{url}/chat/completions", json=payload)
            if resp.status_code >= 400 and use_json and "response_format" in resp.text:
                # Старые/мелкие модели не поддерживают response_format —
                # повторяем без него, парсер вытащит JSON из текста.
                payload.pop("response_format", None)
                resp = client.post(f"{url}/chat/completions", json=payload)
        if resp.status_code >= 400:
            raise ProviderError(
                "Provider error",
                i18n.t(
                    "Ошибка {provider} ({status}): {body}",
                    provider=config.PROVIDER_NAMES.get(provider, provider),
                    status=resp.status_code,
                    body=resp.text[:300],
                ),
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
            "Provider timeout",
            i18n.t(
                "Превышено время ожидания ответа от {url} ({timeout} c)",
                url=url,
                timeout=timeout,
            ),
        ) from exc
    except httpx.HTTPError as exc:
        raise ProviderError(
            "Provider unreachable",
            i18n.t(
                "Не удалось подключиться к {provider} на {url}: {error}",
                provider=provider,
                url=url,
                error=exc,
            ),
        ) from exc
    except ValueError as exc:
        raise ProviderError(
            "Invalid response",
            i18n.t("Провайдер вернул некорректный JSON: {error}", error=exc),
        ) from exc


def _headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers
