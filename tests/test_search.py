from src.search import bm25_search, _rrf_score


def _make_chunks(texts: list[str]) -> list[dict]:
    return [
        {
            "text": t,
            "meta": {"start": float(i * 5), "end": float(i * 5 + 4)},
            "chunk_id": i,
        }
        for i, t in enumerate(texts)
    ]


def test_bm25_ranks_relevant_first():
    chunks = _make_chunks([
        "python programming tutorial for beginners",
        "cooking recipe for chocolate cake",
        "python data science and machine learning",
        "gardening tips for spring flowers",
    ])
    results = bm25_search(chunks, "python programming", top_k=4)
    top_texts = [r["text"] for r in results[:2]]
    assert any("python" in t for t in top_texts)


def test_bm25_returns_top_k():
    chunks = _make_chunks([f"document number {i}" for i in range(20)])
    results = bm25_search(chunks, "document", top_k=5)
    assert len(results) <= 5


def test_rrf_score_decreases_with_rank():
    scores = [_rrf_score(r) for r in range(10)]
    assert all(scores[i] > scores[i + 1] for i in range(len(scores) - 1))


def test_rrf_score_positive():
    assert _rrf_score(0) > 0
    assert _rrf_score(1000) > 0
