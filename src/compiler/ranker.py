"""
Relevance ranker for knowledge objects.

Scores combine:
  semantic_score   — cosine similarity from ChromaDB (0–1)
  type_match       — does this object type match query intent?
  confidence       — extractor's confidence in the object
  entity_overlap   — query terms that match object entities
  recency_bias     — slight penalty for very late timestamps (often outro fluff)

No LLM. Pure signal combination.
"""

from ..knowledge.schema import KnowledgeObject, KnowledgeType

_WEIGHTS = {
    "semantic":       0.45,
    "type_match":     0.25,
    "confidence":     0.15,
    "entity_overlap": 0.10,
    "recency":        0.05,
}


def _entity_overlap(obj: KnowledgeObject, query_terms: set[str]) -> float:
    if not obj.entities or not query_terms:
        return 0.0
    entity_words = set()
    for e in obj.entities:
        entity_words.update(e.lower().split())
    matches = len(entity_words & query_terms)
    return min(matches / max(len(query_terms), 1), 1.0)


def _recency_score(timestamp: float, total_duration: float) -> float:
    """Prefer mid-video content; slight penalty for last 10% (outro)."""
    if total_duration <= 0:
        return 1.0
    rel = timestamp / total_duration
    if rel > 0.90:
        return 0.6
    return 1.0


def score(
    obj: KnowledgeObject,
    semantic_score: float,
    query: str,
    priority_types: list[KnowledgeType],
    total_duration: float = 0.0,
) -> float:
    query_terms = set(query.lower().split())

    type_match = 1.0 if obj.type in priority_types else 0.2
    entity = _entity_overlap(obj, query_terms)
    recency = _recency_score(obj.timestamp, total_duration)

    return (
        semantic_score * _WEIGHTS["semantic"]
        + type_match   * _WEIGHTS["type_match"]
        + obj.confidence * _WEIGHTS["confidence"]
        + entity       * _WEIGHTS["entity_overlap"]
        + recency      * _WEIGHTS["recency"]
    )


def rank(
    candidates: list[tuple[KnowledgeObject, float]],  # (obj, semantic_score)
    query: str,
    priority_types: list[KnowledgeType],
    total_duration: float = 0.0,
) -> list[tuple[KnowledgeObject, float]]:
    """Returns (object, final_score) sorted descending."""
    scored = [
        (obj, score(obj, sem, query, priority_types, total_duration))
        for obj, sem in candidates
    ]
    return sorted(scored, key=lambda x: x[1], reverse=True)
