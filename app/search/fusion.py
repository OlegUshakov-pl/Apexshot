"""Reciprocal Rank Fusion — слияние ранжированных списков.

score[id] = Σ 1 / (k + rank_i), k=60 (стандартная константа TREC),
rank_i — позиция id в i-том списке (0-based + 1).
"""
from __future__ import annotations

RRF_K = 60


def rrf_merge(
    *ranked_lists: list[tuple[str, float]],
    k: int = RRF_K,
) -> list[tuple[str, float]]:
    """Сливает списки [(id, _score_ignored)] в один по RRF.

    Оригинальные score не используются — только позиции в списках.
    Если id встречается в нескольких списках, вклад учитывается
    от каждого списка отдельно.
    """
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, (doc_id, _score) in enumerate(ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda p: p[1], reverse=True)
