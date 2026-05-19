"""
Knowledge Compiler pipeline.

This is NOT a RAG pipeline. The difference:

  RAG:              text chunks → retrieve similar chunks → send to LLM
  Knowledge Compiler: raw info → extract typed knowledge objects
                      → rank by query relevance → structured brief → LLM

LLM usage:
  1. Haiku (once per video) — extract KnowledgeObjects from transcript
  2. Sonnet (once per query) — answer from structured KnowledgeBrief

Zero LLM at retrieval / ranking time.

Flow:
  Input: video_id + query
    → [cache check]
    → fetch + clean transcript
    → compress transcript text (for extraction input)
    → [if not indexed] Haiku extraction → save KnowledgeObjects
    → parse query → identify priority knowledge types
    → semantic search + type-aware retrieval
    → rank knowledge objects
    → assemble structured KnowledgeBrief (within token budget)
    → Sonnet: answer from brief
    → cache result
"""

import os
import re

import anthropic
from dotenv import load_dotenv

from . import cache
from .compiler.assembler import assemble, build_prompt
from .compiler.query_parser import primary_types
from .compiler.ranker import rank
from .compression import count_tokens
from .knowledge.extractor import extract
from .knowledge.store import load_all, save, semantic_search, video_indexed
from .transcript import fetch_transcript, merge_into_chunks

load_dotenv()

_SONNET_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
_CONTEXT_BUDGET = int(os.getenv("CONTEXT_BUDGET_TOKENS", "6000"))


def _extract_video_id(url_or_id: str) -> str:
    patterns = [
        r"(?:v=|youtu\.be/)([A-Za-z0-9_\-]{11})",
        r"^([A-Za-z0-9_\-]{11})$",
    ]
    for pat in patterns:
        m = re.search(pat, url_or_id)
        if m:
            return m.group(1)
    raise ValueError(f"Cannot extract video ID from: {url_or_id}")


def _compress_for_extraction(chunks: list[dict]) -> str:
    """
    Produce a compact transcript string for the Haiku extraction call.
    Ordered by time; timestamps included so extractor can set them.
    """
    lines = []
    for chunk in sorted(chunks, key=lambda c: c.get("start", 0)):
        ts = int(chunk.get("start", 0))
        lines.append(f"[{ts}s] {chunk['text']}")
    return "\n".join(lines)


def run(
    video_url_or_id: str,
    query: str,
    title: str = "",
    force_refresh: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Execute the Knowledge Compiler pipeline.

    Returns:
        {
            "answer": str,
            "cached": bool,
            "knowledge_objects_used": int,
            "types_in_brief": list[str],
            "context_tokens": int,
            "cost": dict,
        }
    """
    video_id = _extract_video_id(video_url_or_id)

    # ── 1. Cache check ───────────────────────────────────────────────────────
    if not force_refresh:
        hit = cache.get(video_id, query)
        if hit:
            if verbose:
                print("[cache] HIT")
            return {**hit, "cached": True}

    # ── 2. Transcript fetch + chunk ──────────────────────────────────────────
    if verbose:
        print(f"[transcript] Fetching {video_id}...")
    segments = fetch_transcript(video_id)
    chunks = merge_into_chunks(segments, chunk_tokens=120, overlap_segments=1)
    if verbose:
        print(f"[transcript] {len(segments)} segments → {len(chunks)} chunks")

    # ── 3. Knowledge extraction (Haiku, one-time per video) ──────────────────
    if not video_indexed(video_id) or force_refresh:
        if verbose:
            print("[extract] Running Haiku knowledge extraction...")
        compressed = _compress_for_extraction(chunks)
        objects = extract(video_id, compressed, verbose=verbose)
        save(objects)
    else:
        if verbose:
            objects = load_all(video_id)
            print(f"[extract] Using cached knowledge base ({len(objects)} objects)")

    # ── 4. Query parsing ─────────────────────────────────────────────────────
    priority = primary_types(query, top_n=4)
    if verbose:
        print(f"[query] Priority types: {priority}")

    # ── 5. Semantic retrieval (type-aware) ───────────────────────────────────
    candidates = semantic_search(video_id, query, top_k=40)
    if verbose:
        print(f"[search] {len(candidates)} candidates retrieved")

    # ── 6. Rank ──────────────────────────────────────────────────────────────
    total_duration = segments[-1].end if segments else 0.0
    ranked = rank(candidates, query, priority, total_duration)

    # ── 7. Assemble structured KnowledgeBrief ────────────────────────────────
    brief = assemble(ranked, query, video_id, priority, _CONTEXT_BUDGET)
    if verbose:
        types_present = list(brief.objects_by_type.keys())
        total_obj = sum(len(v) for v in brief.objects_by_type.values())
        print(f"[brief] {total_obj} objects, types: {types_present}, "
              f"~{brief.total_tokens} tokens")

    # ── 8. Sonnet: answer from structured brief ──────────────────────────────
    system_prompt, user_prompt = build_prompt(brief, title)
    context_tokens = count_tokens(system_prompt) + count_tokens(user_prompt)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model=_SONNET_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    answer = response.content[0].text
    output_tokens = response.usage.output_tokens

    # Cost: Sonnet $3/$15 per MTok
    cost_usd = (context_tokens / 1e6 * 3.0) + (output_tokens / 1e6 * 15.0)
    cost = {
        "input_tokens": context_tokens,
        "output_tokens": output_tokens,
        "total_usd": round(cost_usd, 5),
        "total_jpy": round(cost_usd * 150, 2),
    }

    result = {
        "answer": answer,
        "cached": False,
        "knowledge_objects_used": sum(len(v) for v in brief.objects_by_type.values()),
        "types_in_brief": list(brief.objects_by_type.keys()),
        "context_tokens": context_tokens,
        "cost": cost,
        "video_id": video_id,
    }

    # ── 9. Cache result ──────────────────────────────────────────────────────
    cache.set(video_id, query, result)
    return result
