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
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

from . import cache
from .compiler.assembler import assemble, build_prompt
from .compiler.query_parser import primary_types
from .compiler.ranker import rank
from .compression import count_tokens
from .knowledge.extractor import extract
from .knowledge.merger import merge_objects
from .knowledge.store import load_all, save, semantic_search, semantic_search_multi, video_indexed
from .llm import get_answer_client, provider_label
from .transcript import fetch_transcript, merge_into_chunks, CloudIpBlockedError
from .youtube_search import search as youtube_search

load_dotenv()

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

    # ── 8. LLM: answer from structured brief ─────────────────────────────────
    system_prompt, user_prompt = build_prompt(brief, title)
    context_tokens = count_tokens(system_prompt) + count_tokens(user_prompt)

    llm = get_answer_client()
    resp = llm.complete(system_prompt, user_prompt, max_tokens=1024)
    answer = resp.text

    if verbose:
        print(f"[answer] {provider_label()} | {resp.input_tokens}+{resp.output_tokens} tok"
              f" | ¥{resp.cost_usd * 150:.2f}")

    cost = {
        "input_tokens": resp.input_tokens,
        "output_tokens": resp.output_tokens,
        "total_usd": round(resp.cost_usd, 5),
        "total_jpy": round(resp.cost_usd * 150, 2),
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


# ── Search pipeline ──────────────────────────────────────────────────────────

def _process_video(video_id: str, force_refresh: bool, verbose: bool) -> list:
    """
    Fetch transcript, extract knowledge objects, and persist for a single video.
    Returns the list of KnowledgeObjects stored (or already present).
    Called in parallel by run_search.
    """
    if video_indexed(video_id) and not force_refresh:
        if verbose:
            objs = load_all(video_id)
            print(f"[extract:{video_id}] Already indexed ({len(objs)} objects)")
        return load_all(video_id)

    if verbose:
        print(f"[transcript:{video_id}] Fetching...")
    try:
        segments = fetch_transcript(video_id)
    except CloudIpBlockedError:
        raise  # propagate — let run_search report the real cause
    except Exception as exc:
        if verbose:
            print(f"[transcript:{video_id}] No transcript: {exc}")
        raise  # propagate with real error — run_search will surface it
    chunks = merge_into_chunks(segments, chunk_tokens=120, overlap_segments=1)
    if verbose:
        print(f"[transcript:{video_id}] {len(segments)} segments → {len(chunks)} chunks")

    if verbose:
        print(f"[extract:{video_id}] Running Haiku extraction...")
    compressed = _compress_for_extraction(chunks)
    objects = extract(video_id, compressed, verbose=verbose)
    save(objects)
    return objects


def run_search(
    query: str,
    max_videos: int = 3,
    title: str = "",
    force_refresh: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Full pipeline: YouTube search → multi-video knowledge extraction → unified brief → answer.

    Flow:
        1. Cache check (keyed by "search::{query}")
        2. Search YouTube for query → up to max_videos results
        3. For each video (parallel): fetch transcript + Haiku extraction
        4. Load all KnowledgeObjects for all videos
        5. Cross-video deduplication via merger
        6. Semantic search across all videos' ChromaDB collections (merged)
        7. Rank the unified candidate pool
        8. Assemble structured KnowledgeBrief
        9. Sonnet answer
        10. Cache result

    Returns:
        {
            "answer": str,
            "cached": bool,
            "videos_searched": list[dict],   # [{id, title, duration}, ...]
            "knowledge_objects_used": int,
            "types_in_brief": list[str],
            "context_tokens": int,
            "cost": dict,
        }
    """
    # ── 1. Cache check ──────────────────────────────────────────────────────
    _SEARCH_NS = "search"
    if not force_refresh:
        hit = cache.get(_SEARCH_NS, query)
        if hit:
            if verbose:
                print("[cache] HIT (search query)")
            return {**hit, "cached": True}

    # ── 2. YouTube search ───────────────────────────────────────────────────
    if verbose:
        print(f"[search] Querying YouTube: '{query}' (max {max_videos})...")
    videos = youtube_search(query, max_results=max_videos)
    if not videos:
        return {
            "answer": "No YouTube videos found for the query.",
            "cached": False,
            "videos_searched": [],
            "knowledge_objects_used": 0,
            "types_in_brief": [],
            "context_tokens": 0,
            "cost": {"input_tokens": 0, "output_tokens": 0, "total_usd": 0.0, "total_jpy": 0.0},
        }
    if verbose:
        for v in videos:
            print(f"[search] Found: {v['id']} — {v['title']} ({v['duration']}s)")

    # ── 3. Parallel transcript fetch + knowledge extraction ─────────────────
    video_ids = [v["id"] for v in videos]
    objects_by_video: dict[str, list] = {}

    transcript_errors: list[str] = []
    ip_blocked_count = 0
    with ThreadPoolExecutor(max_workers=min(len(video_ids), 4)) as pool:
        future_to_id = {
            pool.submit(_process_video, vid, force_refresh, verbose): vid
            for vid in video_ids
        }
        for future in as_completed(future_to_id):
            vid = future_to_id[future]
            try:
                objects_by_video[vid] = future.result()
            except CloudIpBlockedError as exc:
                if verbose:
                    print(f"[warn] Video {vid} IP blocked: {exc}")
                objects_by_video[vid] = []
                ip_blocked_count += 1
                transcript_errors.append(f"{vid}: {exc}")
            except Exception as exc:
                if verbose:
                    print(f"[warn] Video {vid} failed: {exc}")
                objects_by_video[vid] = []
                transcript_errors.append(f"{vid}: {type(exc).__name__}: {exc}")

    # ── 4. Load all objects (ensure all are from store) ─────────────────────
    for vid in video_ids:
        if not objects_by_video.get(vid):
            objects_by_video[vid] = load_all(vid)

    # ── 5. Cross-video deduplication ─────────────────────────────────────────
    total_objects = sum(len(v) for v in objects_by_video.values())
    if total_objects == 0:
        error_detail = "; ".join(transcript_errors) if transcript_errors else "unknown"
        if ip_blocked_count > 0:
            raise RuntimeError(
                "YouTube is blocking transcript requests from this server's IP address. "
                "To fix: set WEBSHARE_PROXY_USERNAME + WEBSHARE_PROXY_PASSWORD "
                f"(webshare.io free tier) or YOUTUBE_PROXY_HTTP env var. Detail: {error_detail}"
            )
        raise RuntimeError(
            f"Could not fetch transcripts for any of the found videos. Detail: {error_detail}"
        )
    merged = merge_objects(objects_by_video)
    if verbose:
        total_before = sum(len(v) for v in objects_by_video.values())
        print(f"[merge] {total_before} objects → {len(merged)} after dedup")

    # ── 6. Query parsing ─────────────────────────────────────────────────────
    priority = primary_types(query, top_n=4)
    if verbose:
        print(f"[query] Priority types: {priority}")

    # ── 7. Semantic search across all videos' collections ────────────────────
    indexed_ids = [vid for vid in video_ids if video_indexed(vid)]
    candidates_raw = semantic_search_multi(indexed_ids, query, top_k=40)

    # Filter candidates to only those present in the merged (deduplicated) pool
    merged_ids = {obj.id for obj in merged}
    candidates = [(obj, score) for obj, score in candidates_raw if obj.id in merged_ids]
    if verbose:
        print(f"[search] {len(candidates_raw)} raw candidates → "
              f"{len(candidates)} after dedup filter")

    # ── 8. Rank ──────────────────────────────────────────────────────────────
    ranked = rank(candidates, query, priority, total_duration=0.0)

    # ── 9. Assemble structured KnowledgeBrief ────────────────────────────────
    # Use a synthetic "multi-video" identifier for the brief
    multi_id = "+".join(video_ids[:3])
    brief = assemble(ranked, query, multi_id, priority, _CONTEXT_BUDGET)
    if verbose:
        types_present = list(brief.objects_by_type.keys())
        total_obj = sum(len(v) for v in brief.objects_by_type.values())
        print(f"[brief] {total_obj} objects, types: {types_present}, "
              f"~{brief.total_tokens} tokens")

    # ── 10. LLM: answer from structured brief ────────────────────────────────
    video_titles = ", ".join(
        v["title"] for v in videos if v["id"] in indexed_ids
    )
    effective_title = title or video_titles
    system_prompt, user_prompt = build_prompt(brief, effective_title)
    context_tokens = count_tokens(system_prompt) + count_tokens(user_prompt)

    llm = get_answer_client()
    resp = llm.complete(system_prompt, user_prompt, max_tokens=1024)
    answer = resp.text

    if verbose:
        print(f"[answer] {provider_label()} | {resp.input_tokens}+{resp.output_tokens} tok"
              f" | ¥{resp.cost_usd * 150:.2f}")

    cost = {
        "input_tokens": resp.input_tokens,
        "output_tokens": resp.output_tokens,
        "total_usd": round(resp.cost_usd, 5),
        "total_jpy": round(resp.cost_usd * 150, 2),
    }

    result = {
        "answer": answer,
        "cached": False,
        "videos_searched": videos,
        "knowledge_objects_used": sum(len(v) for v in brief.objects_by_type.values()),
        "types_in_brief": list(brief.objects_by_type.keys()),
        "context_tokens": context_tokens,
        "cost": cost,
    }

    # ── 11. Cache result ──────────────────────────────────────────────────────
    cache.set(_SEARCH_NS, query, result)
    return result
