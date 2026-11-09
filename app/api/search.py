"""HTTP-эндпоинты гибридного поиска (POST /api/search)."""
from __future__ import annotations

import time

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..search import hybrid_search

api = APIRouter(prefix="/api")


class SearchRequest(BaseModel):
    query: str = ""
    top_k: int = Field(default=10, ge=1, le=100)


@api.post("/search")
def search(req: SearchRequest) -> dict:
    started = time.perf_counter()
    results = hybrid_search(req.query, req.top_k)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "results": results,
        "total": len(results),
        "search_ms": round(elapsed_ms, 1),
    }
