"""Обёртка над Ollama API для поиска: эмбеддинги query и документов.

Используется httpx (синхронный клиент). В тестах подменяется
transport'ом через httpx.MockTransport — см. tests/test_search.py.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from .. import config

logger = logging.getLogger("search.ollama")


class OllamaUnavailable(Exception):
    """Ollama недоступна, модель не готова или таймаут."""


class OllamaClient:
    def __init__(
        self,
        base_url: str = "",
        model: str = "",
        timeout: float = 0.0,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.base_url = (base_url or config.SEARCH_OLLAMA_URL).rstrip("/")
        self.model = model or config.SEARCH_EMBED_MODEL
        self.timeout = timeout or config.SEARCH_EMBED_TIMEOUT
        self._client = httpx.Client(
            base_url=self.base_url, transport=transport, timeout=self.timeout
        )

    # ---------------------------------------------------------------- health
    def is_available(self) -> bool:
        """True, если Ollama отвечает и модель видна в списке."""
        try:
            resp = self._client.get("/api/tags", timeout=5)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Ollama недоступна на %s: %s", self.base_url, exc)
            return False
        try:
            models = [m.get("name", "") for m in resp.json().get("models", [])]
        except ValueError:
            return False
        # имена моделей вида "bge-m3" или "bge-m3:latest"
        return any(m == self.model or m.split(":")[0] == self.model for m in models)

    def ensure_model(self, timeout: float = 0.0) -> bool:
        """Проверяет наличие модели, при отсутствии делает ollama pull."""
        timeout = timeout or config.SEARCH_PULL_TIMEOUT
        try:
            resp = self._client.get("/api/tags", timeout=10)
            resp.raise_for_status()
            models = [m.get("name", "") for m in resp.json().get("models", [])]
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "Не удалось получить список моделей Ollama: %s", exc
            )
            return False
        if not any(m == self.model or m.split(":")[0] == self.model for m in models):
            try:
                resp = self._client.post(
                    "/api/pull",
                    json={"model": self.model, "stream": False},
                    timeout=timeout,
                )
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning(
                    "Не удалось скачать модель %s: %s", self.model, exc
                )
                return False
        return True

    # ---------------------------------------------------------------- embed
    def embed(self, texts: list[str]) -> list[list[float]]:
        """POST /api/embed -> список векторов (по одному на входную строку)."""
        if not texts:
            return []
        try:
            resp = self._client.post(
                "/api/embed",
                json={"model": self.model, "input": texts},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise OllamaUnavailable(f"Ollama embed failed: {exc}") from exc
        except ValueError as exc:
            raise OllamaUnavailable(f"Ollama embed: невалидный ответ: {exc}") from exc
        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise OllamaUnavailable("Ollama embed: пустой/некорректный ответ")
        return embeddings


_client: Optional[OllamaClient] = None


def get_client() -> OllamaClient:
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client


def set_client(client: Optional[OllamaClient]) -> None:
    """Подмена клиента (в тестах) или сброс (client=None -> пересоздание)."""
    global _client
    _client = client
