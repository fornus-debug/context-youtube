"""
Main Context OS pipeline orchestrator.

Flow:
  YouTube ID + Query
    → [cache check]
    → transcript fetch + chunk
    → embed + store (once per video)
    → hybrid search
    → score-based attention
    → rule-based compression
    → prompt assembly
    → Claude Sonnet (single call)
    → cache result
    → return
"""

import os
from typing import Optional

import anthropic
from dotenv import load_dotenv

from . import cache, embeddings
from .compression import compress_chunks, deduplicate, score_chunks, count_tokens
from .prompt import assemble_prompt, estimate_cost
from .search import hybrid_search
from .transcript import fetch_transcript, merge_into_chunks

load_dotenv()

_CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
_CONTEXT_BUDGET = int(os.getenv("CONTEXT_BUDGET_TOKENS", "6000"))


def _extract_video_id(url_or_id: str) -> str:
    """Accept full URL or bare video ID."""
    import re
    patterns = [
        r"(?:v=|youtu\.be/)([A-Za-z0-9_\-]{11})",
        r"^([A-Za-z0-9_\-]{11})$",
    ]
    for pat in patterns:
        m = re.search(pat, url_or_id)
        if m:
            return m.group(1)
    raise ValueError(f"Cannot extract video ID from: {url_or_id}")


def run(
    video_url_or_id: str,
    query: str,
    title: str = "",
    force_refresh: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Execute the full pipeline and return a result dict.

    Returns:
        {
            "answer": str,
            "cached": bool,
            "cost": dict,
            "chunks_used": int,
            "context_tokens": int,
        }
    """
    video_id = _extract_video_id(video_url_or_id)

    # ── 1. Cache check ───────────────────────────────────────────────────────
    if not force_refresh:
        cached = cache.get(video_id, query)
        if cached:
            if verbose:
                print(f"[cache] HIT for video={video_id}")
            return {**cached, "cached": True}

    # ── 2. Transcript fetch + chunking ───────────────────────────────────────
    if verbose:
        print(f"[transcript] Fetching {video_id}...")
    segments = fetch_transcript(video_id)
    if not segments:
        raise ValueError("No transcript segments retrieved.")
    chunks = merge_into_chunks(segments, chunk_tokens=120, overlap_segments=1)
    if verbose:
        print(f"[transcript] {len(segments)} segments → {len(chunks)} chunks")

    # ── 3. Embed + store (skip if already indexed) ───────────────────────────
    if not embeddings.collection_exists(video_id) or force_refresh:
        if verbose:
            print(f"[embed] Indexing {len(chunks)} chunks...")
        embeddings.embed_and_store(video_id, chunks)
    else:
        if verbose:
            print(f"[embed] Using existing index for {video_id}")

    # ── 4. Hybrid search ─────────────────────────────────────────────────────
    if verbose:
        print(f"[search] Hybrid search for: '{query}'")
    search_results = hybrid_search(video_id, chunks, query, top_k=20)

    # ── 5. Score-based attention ─────────────────────────────────────────────
    total_duration = segments[-1].end if segments else 0.0
    scored = score_chunks(search_results, query, total_duration)

    # ── 6. Deduplication ─────────────────────────────────────────────────────
    deduped = deduplicate(scored)

    # ── 7. Rule-based compression ────────────────────────────────────────────
    compressed = compress_chunks(deduped, query, budget_tokens=_CONTEXT_BUDGET)
    if verbose:
        total_tok = sum(c.get("tokens", 0) for c in compressed)
        print(f"[compress] {len(compressed)} chunks, ~{total_tok} tokens")

    # ── 8. Prompt assembly ───────────────────────────────────────────────────
    system_prompt, user_prompt = assemble_prompt(compressed, query, video_id, title)
    context_tokens = count_tokens(system_prompt) + count_tokens(user_prompt)
    if verbose:
        print(f"[prompt] Context size: {context_tokens} tokens")

    # ── 9. Claude Sonnet — single call ───────────────────────────────────────
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model=_CLAUDE_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    answer = response.content[0].text
    output_tokens = response.usage.output_tokens

    cost = estimate_cost(context_tokens, output_tokens)

    result = {
        "answer": answer,
        "cached": False,
        "cost": cost,
        "chunks_used": len(compressed),
        "context_tokens": context_tokens,
        "video_id": video_id,
    }

    # ── 10. Cache result ─────────────────────────────────────────────────────
    cache.set(video_id, query, result)

    return result
