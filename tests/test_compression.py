from src.compression import (
    compress_chunks,
    count_tokens,
    deduplicate,
    score_chunks,
)


def _make_chunks(texts: list[str]) -> list[dict]:
    return [
        {
            "text": t,
            "meta": {"start": float(i * 10), "end": float(i * 10 + 9)},
            "relevance_score": 1.0 / (i + 1),
        }
        for i, t in enumerate(texts)
    ]


def test_count_tokens_basic():
    assert count_tokens("hello world") > 0
    assert count_tokens("") == 0


def test_score_chunks_sorted():
    chunks = _make_chunks(["machine learning tutorial", "random unrelated content", "ML algorithms explained"])
    scored = score_chunks(chunks, "machine learning")
    scores = [c["attention_score"] for c in scored]
    assert scores == sorted(scores, reverse=True)


def test_compress_respects_budget():
    long_texts = ["word " * 100] * 20
    chunks = _make_chunks(long_texts)
    for c in chunks:
        c["attention_score"] = 1.0

    compressed = compress_chunks(chunks, "word", budget_tokens=200)
    total = sum(c.get("tokens", count_tokens(c["text"])) for c in compressed)
    assert total <= 220  # allow small overshoot from estimation


def test_deduplicate_removes_near_dups():
    texts = [
        "the quick brown fox jumps over the lazy dog",
        "the quick brown fox jumps over the lazy dog today",  # near-dup
        "completely different content about machine learning",
    ]
    chunks = _make_chunks(texts)
    result = deduplicate(chunks, sim_threshold=0.7)
    assert len(result) == 2


def test_deduplicate_keeps_unique():
    texts = [
        "machine learning algorithms for classification",
        "cooking pasta with tomato sauce and basil",
        "quantum physics theories about entanglement",
        "javascript frontend development with react",
        "photography tips for landscape shooting",
    ]
    chunks = _make_chunks(texts)
    result = deduplicate(chunks)
    assert len(result) == 5
