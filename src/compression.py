"""
Score-based attention + rule-based compression.
No LLM — purely algorithmic pruning to fit context budget.
"""

import os
import re
from collections import Counter

_BUDGET = int(os.getenv("CONTEXT_BUDGET_TOKENS", "6000"))


def count_tokens(text: str) -> int:
    """Approximate token count: words * 1.35 (empirically close to Claude tokenizer)."""
    if not text:
        return 0
    return int(len(text.split()) * 1.35)


# ── Score-based attention ────────────────────────────────────────────────────

def _query_term_density(text: str, query_terms: set[str]) -> float:
    """Fraction of words that match query terms."""
    words = text.lower().split()
    if not words:
        return 0.0
    matches = sum(1 for w in words if w in query_terms)
    return matches / len(words)


def _sentence_position_score(meta: dict, total_duration: float) -> float:
    """
    Slight preference for intro/conclusion (often contain summary info).
    Returns 0.0–0.2 bonus.
    """
    if total_duration <= 0:
        return 0.0
    mid = (meta.get("start", 0) + meta.get("end", meta.get("start", 0))) / 2
    relative = mid / total_duration
    # U-shaped: high at 0 and 1, low in the middle
    return 0.2 * (1.0 - abs(relative - 0.5) * 2) * (-1) + 0.2


def score_chunks(
    chunks: list[dict],
    query: str,
    total_duration: float = 0.0,
) -> list[dict]:
    """
    Assign a composite attention score to each chunk.
    Components: relevance_score (from hybrid search) + query density + position.
    """
    query_terms = set(query.lower().split())
    scored = []
    for chunk in chunks:
        density = _query_term_density(chunk["text"], query_terms)
        position = _sentence_position_score(chunk.get("meta", {}), total_duration)
        base = chunk.get("relevance_score", 0.0)
        chunk["attention_score"] = base + 0.15 * density + position
        scored.append(chunk)
    scored.sort(key=lambda x: x["attention_score"], reverse=True)
    return scored


# ── Rule-based compression ───────────────────────────────────────────────────

_REDUNDANT_PHRASES = re.compile(
    r"\b(as i (said|mentioned|was saying)|like i said|"
    r"you know what i mean|let me (tell|show) you|"
    r"so basically|anyway|alright so)\b",
    re.IGNORECASE,
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _compress_text(text: str) -> str:
    text = _REDUNDANT_PHRASES.sub("", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _drop_low_density_sentences(text: str, query_terms: set[str], threshold: float = 0.05) -> str:
    """Remove individual sentences with near-zero query term overlap."""
    sentences = _SENTENCE_SPLIT.split(text)
    kept = []
    for sent in sentences:
        words = set(sent.lower().split())
        if not words:
            continue
        density = len(words & query_terms) / len(words)
        if density >= threshold or len(sent.split()) < 6:
            kept.append(sent)
    return " ".join(kept) if kept else text


def compress_chunks(
    chunks: list[dict],
    query: str,
    budget_tokens: int = _BUDGET,
) -> list[dict]:
    """
    Rule-based compression pipeline:
    1. Drop redundant phrases
    2. Drop low-density sentences
    3. Truncate to token budget
    Result is ordered by attention_score descending.
    """
    query_terms = set(query.lower().split())
    compressed: list[dict] = []
    used_tokens = 0

    for chunk in chunks:
        text = _compress_text(chunk["text"])
        text = _drop_low_density_sentences(text, query_terms)
        if not text:
            continue
        tokens = count_tokens(text)
        if used_tokens + tokens > budget_tokens:
            # Partial inclusion: fit what we can
            remaining = budget_tokens - used_tokens
            if remaining < 30:
                break
            words = text.split()
            # Rough trim: 0.75 words per token
            trim = int(remaining * 0.75)
            text = " ".join(words[:trim])
            tokens = count_tokens(text)

        compressed.append({**chunk, "text": text, "tokens": tokens})
        used_tokens += tokens
        if used_tokens >= budget_tokens:
            break

    return compressed


# ── Deduplication ────────────────────────────────────────────────────────────

def deduplicate(chunks: list[dict], sim_threshold: float = 0.7) -> list[dict]:
    """Remove near-duplicate chunks using simple word-level Jaccard."""
    seen: list[set[str]] = []
    unique: list[dict] = []
    for chunk in chunks:
        words = set(chunk["text"].lower().split())
        is_dup = False
        for s in seen:
            if not s:
                continue
            j = len(words & s) / len(words | s)
            if j >= sim_threshold:
                is_dup = True
                break
        if not is_dup:
            unique.append(chunk)
            seen.append(words)
    return unique
