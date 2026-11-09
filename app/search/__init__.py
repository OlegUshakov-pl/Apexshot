"""Гибридный поиск по локальным слепкам: ChromaDB + BM25 + RRF.

Пакет framework-agnostic: UI (эндпоинт FastAPI) вызывает только
hybrid_search() и не знает деталей реализации.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .. import config
from . import bm25_index, corpus, vector_index
from .bm25_index import tokenize
from .fusion import rrf_merge
from .ollama_client import OllamaUnavailable, get_client

logger = logging.getLogger("search")

DEFAULT_TOP_K = 10
SNIPPET_CHARS = 200
MATCHABLE_FIELDS = ("title", "summary", "facts", "entities")

_field_words_cache: dict[str, frozenset[str]] = {}


def _snapshot_path(doc_id: str) -> Path:
    return config.SNAPSHOTS_DIR / f"{doc_id}.json"


class HybridSearch:
    """Ядро поиска. Состояние: векторный индекс + BM25 (оба можно пересобрать)."""

    def __init__(self) -> None:
        self._degraded = False  # Ollama недоступна -> результаты BM25-only

    # ---------------------------------------------------------------- state
    @property
    def degraded(self) -> bool:
        return self._degraded

    def status(self) -> dict[str, Any]:
        client = get_client()
        return {
            "ollama": {"available": client.is_available(), "model": client.model},
            "chroma_available": vector_index.is_available(),
            "vector_index_size": vector_index.count(),
            "bm25_built": bm25_index.is_built(),
            "bm25_docs": len(bm25_index.all_docs()),
            "degraded": self._degraded,
        }

    # ---------------------------------------------------------------- build
    def rebuild(self) -> dict[str, Any]:
        """Полный пересбор обоих индексов из локальных JSON-слепков."""
        bm25_index.rebuild()
        ok = vector_index.rebuild(get_client(), docs=corpus.load_documents())
        self._degraded = not ok
        logger.info("Гибридный индекс: rebuild ok=%s, degraded=%s", ok, self._degraded)
        return self.status()

    def on_snapshot_saved(self, doc_id: str) -> None:
        """После генерации нового слепка: добавить в индексы."""
        path = _snapshot_path(doc_id)
        doc = corpus.load_file(path)
        bm25_index.add_document(doc_id)
        if doc is not None:
            vector_index.upsert(doc, get_client())

    def on_snapshot_deleted(self, doc_id: str) -> None:
        """После удаления локального слепка: убрать из индексов."""
        bm25_index.remove_document(doc_id)
        vector_index.delete(doc_id)

    # ---------------------------------------------------------------- search
    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> list[dict[str, Any]]:
        top_k = max(1, min(int(top_k or DEFAULT_TOP_K), 100))
        tokens = tokenize(query)
        bm25_index.ensure_built()

        if not tokens:
            # пустой запрос — без ранжирования: свежие слепки
            return self._recent(top_k)

        # --- векторная часть (ChromaDB + Ollama)
        vec_hits: list[tuple[str, float]] = []
        degraded = False
        if vector_index.is_available():
            try:
                embedding = get_client().embed([query])[0]
            except OllamaUnavailable as exc:
                logger.warning(
                    "Эмбеддинг запроса недоступен: %s — результаты будут BM25-only", exc
                )
                degraded = True
            else:
                vec_hits = vector_index.query(embedding, top_k * 3)
        else:
            degraded = True

        # --- BM25
        bm_hits = bm25_index.search(tokens, top_k)

        # --- RRF-слияние и сортировка по score
        fused = rrf_merge(vec_hits, bm_hits)
        return self._build_results(
            fused, vec_hits, bm_hits, tokens, degraded, top_k
        )

    # -------------------------------------------------------------- helpers
    def _build_results(
        self,
        fused: list[tuple[str, float]],
        vec_hits: list[tuple[str, float]],
        bm_hits: list[tuple[str, float]],
        tokens: list[str],
        degraded: bool,
        top_k: int,
    ) -> list[dict[str, Any]]:
        vec_ids = {doc_id for doc_id, _s in vec_hits}
        bm_ids = {doc_id for doc_id, _s in bm_hits}
        results: list[dict[str, Any]] = []
        for doc_id, rrf_score in fused:
            if len(results) >= top_k:
                break
            doc = bm25_index.get_doc(doc_id)
            if doc is None:
                # документ есть в chroma, но файл уже удалён: пропускаем
                continue
            in_vector = doc_id in vec_ids
            in_bm25 = doc_id in bm_ids
            matched = self._matched_fields(doc, tokens)
            fields: list[str] = []
            if in_vector:
                fields.append("vector")
            # для bm25-only — поля с пересечением; для обоих индексов
            # добавляем matched-поля к "vector"
            if in_bm25 or not in_vector:
                fields.extend(field for field in matched if field not in fields)
            if not fields:
                fields = ["vector"] if in_vector else []
            results.append(
                {
                    "id": doc_id,
                    "title": doc.get("title") or "",
                    "summary": doc.get("summary") or "",
                    "source_url": doc.get("source_url") or "",
                    "score": round(rrf_score, 6),
                    "matched_fields": fields,
                    "snippet": self._snippet(doc, matched, tokens),
                    "degraded": degraded,
                }
            )
        return results

    def _recent(self, top_k: int) -> list[dict[str, Any]]:
        docs = sorted(
            bm25_index.all_docs().values(),
            key=lambda d: d.get("captured_at") or "",
            reverse=True,
        )
        results = []
        for doc in docs[:top_k]:
            results.append(
                {
                    "id": doc["id"],
                    "title": doc.get("title") or "",
                    "summary": doc.get("summary") or "",
                    "source_url": doc.get("source_url") or "",
                    "score": 0.0,
                    "matched_fields": [],
                    "snippet": doc.get("summary") or "",
                    "degraded": self._degraded,
                }
            )
        return results

    def _matched_fields(self, doc: dict[str, Any], tokens: list[str]) -> list[str]:
        """В каких полях (title/summary/facts/entities) есть пересечение токенов."""
        query_words = frozenset(token.lower() for token in tokens)
        if not query_words:
            return []
        matched: list[str] = []
        fields = doc.get("fields") or {}
        for field in MATCHABLE_FIELDS:
            words = _words(str(fields.get(field) or ""))
            if query_words & words:
                matched.append(field)
        return matched

    def _snippet(
        self, doc: dict[str, Any], matched_fields: list[str], tokens: list[str]
    ) -> str:
        """Первые ~200 символов совпавшего факта / саммари."""
        fields = doc.get("fields") or {}
        query_words = frozenset(token.lower() for token in tokens)
        if "facts" in matched_fields:
            fact = self._first_fact_with_match(doc, query_words)
            if fact:
                return fact[:SNIPPET_CHARS]
        for field in ("summary", "title", "entities"):
            if field in matched_fields:
                text = str(fields.get(field) or "")
                if text:
                    return text[:SNIPPET_CHARS]
        text = str(fields.get("summary") or fields.get("title") or "")
        return text[:SNIPPET_CHARS]

    def _first_fact_with_match(
        self, doc: dict[str, Any], query_words: frozenset[str]
    ) -> str:
        fields = doc.get("fields") or {}
        facts = _split_fact_texts(str(fields.get("facts") or ""))
        for fact in facts:
            if fact and query_words & _words(fact.lower()):
                return fact
        return ""


def _words(text: str) -> frozenset[str]:
    cached = _field_words_cache.get(text)
    if cached is None:
        cached = frozenset(tokenize(text))
        if len(_field_words_cache) > 4096:
            _field_words_cache.clear()
        _field_words_cache[text] = cached
    return cached


def _split_fact_texts(joined: str) -> list[str]:
    """Факты склеиваются одним пробелом; для сниппета режем по границам « | »."""
    return [p for p in joined.split(" | ") if p]


core = HybridSearch()


def rebuild_search_index() -> dict[str, Any]:
    return core.rebuild()


def search_status() -> dict[str, Any]:
    return core.status()


def degraded() -> bool:
    return core.degraded


def on_snapshot_saved(doc_id: str) -> None:
    core.on_snapshot_saved(doc_id)


def on_snapshot_deleted(doc_id: str) -> None:
    core.on_snapshot_deleted(doc_id)


def hybrid_search(query: str, top_k: int = DEFAULT_TOP_K) -> list[dict[str, Any]]:
    """Гибридный поиск по локальным слепкам.

    Каждый элемент:
    {id, title, summary, source_url, score, matched_fields, snippet, degraded}
    """
    return core.search(query, top_k)
