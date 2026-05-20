"""
Cross-video knowledge object merger.

Merges KnowledgeObjects from multiple videos into a unified pool
suitable for cross-video querying.  Near-duplicate objects (same
knowledge expressed by different sources) are deduplicated using
word-level Jaccard similarity on the content field.
"""

from .schema import KnowledgeObject


_DEDUP_THRESHOLD = 0.75  # Jaccard similarity above this → treat as duplicate


def _jaccard(a: str, b: str) -> float:
    """Word-level Jaccard similarity between two strings."""
    set_a = set(a.lower().split())
    set_b = set(b.lower().split())
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def merge_objects(
    objects_by_video: dict[str, list[KnowledgeObject]],
) -> list[KnowledgeObject]:
    """
    Merge and cross-video deduplicate KnowledgeObjects.

    Algorithm:
        1. Flatten all objects from all videos into a single list.
        2. Sort by confidence descending so the best representative
           is encountered first and wins deduplication.
        3. For each new object, compare against already-kept objects
           from *different* videos.  If Jaccard(content_a, content_b)
           > 0.75, the lower-confidence object is discarded.
           Objects from the *same* video are never deduplicated against
           each other (different perspectives on the same video are fine).

    Args:
        objects_by_video: Mapping of video_id → list of KnowledgeObjects.

    Returns:
        Deduplicated, unified list of KnowledgeObjects.
    """
    # Flatten
    flat: list[KnowledgeObject] = []
    for objects in objects_by_video.values():
        flat.extend(objects)

    # Sort by confidence desc so higher-confidence wins in dedup
    flat.sort(key=lambda obj: obj.confidence, reverse=True)

    kept: list[KnowledgeObject] = []

    for candidate in flat:
        is_duplicate = False
        for existing in kept:
            # Only deduplicate across videos, not within the same video
            if existing.video_id == candidate.video_id:
                continue
            sim = _jaccard(candidate.content, existing.content)
            if sim > _DEDUP_THRESHOLD:
                # existing has equal-or-higher confidence (due to sort order)
                is_duplicate = True
                break
        if not is_duplicate:
            kept.append(candidate)

    return kept
