"""Векторный индекс: ChromaDB PersistentClient (локально, без Docker).

Коллекция "snapshots". Эмбеддинги — через Ollama (bge-m3).
Если chromadb или Ollama недоступны — поиск деградирует до BM25-only.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from . import corpus

logger = logging.getLogger("search.vector")


class _VectorIndex:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._client: Optional[Any] = None
        self._collection: Optional[Any] = None
        self._chroma_ok = False
        self._built = False

    # ---------------------------------------------------------------- state
    def is_available(self) -> bool:
        return self._chroma_ok and self._collection is not None

    def is_built(self) -> bool:
        return self._built

    def count(self) -> int:
        if not self.is_available() or self._collection is None:
            return 0
        try:
            return int(self._collection.count())
        except Exception as exc:
            logger.warning("ChromaDB count() failed: %s", exc)
            return 0

    def reset(self) -> None:
        with self._lock:
            self._client = None
            self._collection = None
            self._chroma_ok = False
            self._built = False

    # ------------------------------------------------------------ chroma io
    def _open_collection(self) -> Optional[Any]:
        if self._chroma_ok:
            return self._collection
        try:
            import chromadb
        except ImportError as exc:
            logger.warning("chromadb не установлен: %s", exc)
            return None
        try:
            from .. import config

            self._client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
            self._collection = self._client.get_or_create_collection(
                config.SEARCH_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
            self._chroma_ok = True
        except Exception as exc:
            logger.warning("ChromaDB недоступна: %s", exc)
            return None
        return self._collection

    # ---------------------------------------------------------------- build
    def rebuild(self, embedder: Any, docs: Optional[dict[str, Any]] = None) -> bool:
        """Пересоздаёт коллекцию из локальных файлов.

        embedder: объект с методом embed(texts) -> list[list[float]].
        Возвращает True, если удалось построить векторный индекс.
        """
        from .. import config

        collection = self._open_collection()
        if collection is None:
            logger.warning("Векторный индекс недоступен: ChromaDB не открылась")
            return False
        documents = corpus.load_documents() if docs is None else docs

        doc_ids = list(documents.keys())
        texts = [corpus.document_text(documents[i]) for i in doc_ids]
        # пустые embedding-тексты Chroma не приемлет — отфильтровываем
        kept = [(i, t) for i, t in zip(doc_ids, texts) if t.strip()]
        try:
            with self._lock:
                chroma_client = self._client
                try:
                    chroma_client.delete_collection(config.SEARCH_COLLECTION)
                except Exception:
                    pass
                collection = chroma_client.get_or_create_collection(
                    config.SEARCH_COLLECTION,
                    metadata={"hnsw:space": "cosine"},
                )
                self._collection = collection
        except Exception as exc:
            logger.warning("ChromaDB: не удалось пересоздать коллекцию: %s", exc)
            self.reset()
            return False
        if not kept:
            logger.info("Векторный индекс пуст: локальных слепков нет")
            self._built = True
            return True
        try:
            embeddings = embedder.embed([t for _i, t in kept])
        except Exception as exc:
            logger.warning(
                "Ollama недоступна при построении индекса: %s "
                "(векторный поиск деградирует до BM25-only)", exc,
            )
            return False
        if len(embeddings) != len(kept):
            logger.warning("Ollama вернула %d векторов вместо %d", len(embeddings), len(kept))
            return False
        try:
            with self._lock:
                collection.add(
                    ids=[i for i, _t in kept],
                    documents=[t for _i, t in kept],
                    embeddings=embeddings,
                    metadatas=[corpus.metadata(documents[i]) for i, _t in kept],
                )
        except Exception as exc:
            logger.warning("ChromaDB add() failed: %s", exc)
            return False
        logger.info("Векторный индекс построен: %d документов", len(kept))
        self._built = True
        return True

    def upsert(self, doc: dict[str, Any], embedder: Any) -> bool:
        """Добавляет/обновляет один документ после генерации слепка."""
        if not self.is_available() or self._collection is None:
            return False
        text = corpus.document_text(doc)
        if not text.strip():
            return False
        try:
            embeddings = embedder.embed([text])
            self._collection.upsert(
                ids=[doc["id"]],
                documents=[text],
                embeddings=embeddings,
                metadatas=[corpus.metadata(doc)],
            )
            return True
        except Exception as exc:
            logger.warning("ChromaDB upsert(%s) failed: %s", doc.get("id"), exc)
            return False

    def delete(self, doc_id: str) -> bool:
        if not self.is_available() or self._collection is None:
            return False
        try:
            self._collection.delete(ids=[doc_id])
            return True
        except Exception as exc:
            logger.warning("ChromaDB delete(%s) failed: %s", doc_id, exc)
            return False

    # --------------------------------------------------------------- search
    def query(self, embedding: list[float], top_k: int) -> list[tuple[str, float]]:
        """[(id, score)] где score = 1 - cosine_distance."""
        if not self.is_available() or not embedding:
            return []
        try:
            res = self._collection.query(query_embeddings=[embedding], n_results=top_k)
        except Exception as exc:
            logger.warning("ChromaDB query failed: %s", exc)
            return []
        ids = (res.get("ids") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        return [
            (str(doc_id), 1.0 - float(dist))
            for doc_id, dist in zip(ids, dists)
        ]


_index = _VectorIndex()


# ------------------------------------------------------------------ фасад
def is_available() -> bool:
    return _index.is_available()


def is_built() -> bool:
    return _index.is_built()


def count() -> int:
    return _index.count()


def reset() -> None:
    _index.reset()


def rebuild(embedder: Any, docs: Optional[dict[str, Any]] = None) -> bool:
    return _index.rebuild(embedder, docs)


def upsert(doc: dict[str, Any], embedder: Any) -> bool:
    return _index.upsert(doc, embedder)


def delete(doc_id: str) -> bool:
    return _index.delete(doc_id)


def query(embedding: list[float], top_k: int) -> list[tuple[str, float]]:
    return _index.query(embedding, top_k)
