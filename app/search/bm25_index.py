"""BM25 (полнотекстовый) индекс поверх локальных JSON-слепков.

Чистый Python: rank_bm25.BM25Okapi. Индекс держится в памяти;
перестраивается при старте и при каждом изменении слепков.
"""
from __future__ import annotations

import logging
import re
import threading
from typing import Any, Optional

from . import corpus

logger = logging.getLogger("search.bm25")

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Латиница + кириллица + цифры, нижний регистр (согласно task.md)."""
    return _TOKEN_RE.findall((text or "").lower())


class _BM25Index:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._built = False
        self._bm25: Optional[Any] = None
        self._ids: list[str] = []
        self._docs: dict[str, dict[str, Any]] = {}
        self._corpus: list[list[str]] = []

    # ---------------------------------------------------------------- state
    def is_built(self) -> bool:
        return self._built

    def get_doc(self, doc_id: str) -> Optional[dict[str, Any]]:
        return self._docs.get(doc_id)

    def all_docs(self) -> dict[str, dict[str, Any]]:
        return self._docs

    def ensure_built(self) -> None:
        if not self._built:
            self.rebuild()

    # ---------------------------------------------------------------- build
    def rebuild(self, dir_path: Optional[Any] = None) -> int:
        docs = dict(corpus.load_documents(dir_path))
        ids: list[str] = []
        corpus_tokens: list[list[str]] = []
        with self._lock:
            for doc_id, doc in docs.items():
                docs[doc_id] = {
                    "id": doc_id,
                    "title": str(doc.get("title") or ""),
                    "summary": str(doc.get("summary") or ""),
                    "source_url": str(doc.get("source_url") or ""),
                    "fields": corpus.field_texts(doc),
                    "captured_at": corpus.captured_at(doc),
                }
                ids.append(doc_id)
                corpus_tokens.append(tokenize(corpus.document_text(doc)))
        with self._lock:
            self._docs = docs
            self._ids = ids
            self._corpus = corpus_tokens
            self._build_bm25_locked()
            self._built = True
        logger.info("BM25-индекс построен: %d документов", len(ids))
        return len(ids)

    def _build_bm25_locked(self) -> None:
        try:
            from rank_bm25 import BM25Okapi
        except ImportError as exc:
            logger.warning("rank_bm25 не установлен: %s", exc)
            self._bm25 = None
            return
        if not self._ids:
            self._bm25 = None
            return
        self._bm25 = BM25Okapi(self._corpus)

    # --------------------------------------------------------------- search
    def search(self, query_tokens: list[str], top_k: int) -> list[tuple[str, float]]:
        """[(id, score_bm25)] отсортированно по убыванию, не больше top_k*3."""
        self.ensure_built()
        if self._bm25 is None or not query_tokens:
            return []
        try:
            scores = self._bm25.get_scores(query_tokens)
        except ZeroDivisionError:
            # у BM25Okapi бывает ZeroDivisionError, если токенов запроса нет в корпусе
            return []
        if not len(scores):
            return []
        pairs = [
            (self._ids[i], float(scores[i]))
            for i in range(len(self._ids))
            if scores[i] > 0
        ]
        pairs.sort(key=lambda p: p[1], reverse=True)
        return pairs[: max(1, top_k) * 3]


_index = _BM25Index()


# ------------------------------------------------------------------ фасад
def is_built() -> bool:
    return _index.is_built()


def ensure_built() -> None:
    _index.ensure_built()


def rebuild(dir_path: Optional[Any] = None) -> int:
    return _index.rebuild(dir_path)


def add_document(doc_id: str) -> None:
    """После генерации нового слепка — полный пересбор (корпус маленький)."""
    _index.rebuild()


def remove_document(doc_id: str) -> None:
    """После удаления слепка — полный пересбор."""
    _index.rebuild()


def get_doc(doc_id: str) -> Optional[dict[str, Any]]:
    return _index.get_doc(doc_id)


def all_docs() -> dict[str, dict[str, Any]]:
    return _index.all_docs()


def search(query_tokens: list[str], top_k: int) -> list[tuple[str, float]]:
    return _index.search(query_tokens, top_k)
