"""
Hybrid search: BM25 (keyword) + vector similarity, fused via RRF.
No LLM involved — pure algorithmic retrieval.
"""

from rank_bm25 import BM25Okapi

from .embeddings import vector_search


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def bm25_search(
    chunks: list[dict],
    query: str,
    top_k: int = 20,
) -> list[dict]:
    """BM25 over pre-fetched chunks. Returns scored hits."""
    corpus = [_tokenize(c["text"]) for c in chunks]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(_tokenize(query))

    hits = []
    for i, score in enumerate(scores):
        hits.append({
            "text": chunks[i]["text"],
            "meta": chunks[i].get("meta", {}),
            "bm25_score": float(score),
            "chunk_id": chunks[i].get("chunk_id", i),
        })
    hits.sort(key=lambda x: x["bm25_score"], reverse=True)
    return hits[:top_k]


def _rrf_score(rank: int, k: int = 60) -> float:
    """Reciprocal Rank Fusion score."""
    return 1.0 / (k + rank + 1)


def hybrid_search(
    video_id: str,
    chunks: list[dict],
    query: str,
    top_k: int = 15,
    vector_weight: float = 0.6,
    bm25_weight: float = 0.4,
) -> list[dict]:
    """
    Fuse BM25 and vector results via weighted RRF.
    Returns top_k chunks with a combined relevance score.
    """
    vec_hits = vector_search(video_id, query, top_k=top_k * 2)
    bm25_hits = bm25_search(chunks, query, top_k=top_k * 2)

    scores: dict[str, float] = {}
    texts: dict[str, str] = {}
    metas: dict[str, dict] = {}

    for rank, hit in enumerate(vec_hits):
        key = hit["text"]
        scores[key] = scores.get(key, 0.0) + vector_weight * _rrf_score(rank)
        texts[key] = hit["text"]
        metas[key] = hit["meta"]

    for rank, hit in enumerate(bm25_hits):
        key = hit["text"]
        scores[key] = scores.get(key, 0.0) + bm25_weight * _rrf_score(rank)
        if key not in texts:
            texts[key] = hit["text"]
            metas[key] = hit.get("meta", {})

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    return [
        {
            "text": texts[k],
            "meta": metas.get(k, {}),
            "relevance_score": score,
        }
        for k, score in ranked
    ]
