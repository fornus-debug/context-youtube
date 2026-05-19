"""
Knowledge extraction — one LLM call per video (not per query).

Uses Claude Haiku (cheapest model) to process the compressed transcript
and output a typed JSON array of KnowledgeObjects.

Cost: ~$0.005–0.01 per video (one-time, result cached permanently).
Query time: ZERO LLM. All serving is from pre-extracted knowledge.

This is the core distinction from RAG:
  RAG     — LLM at every query
  This    — LLM once per video, algorithmic retrieval forever after
"""

import json
import os
import re
import uuid

import anthropic

from .schema import KnowledgeObject, KnowledgeType, ALL_TYPES

_HAIKU_MODEL = "claude-haiku-4-5-20251001"

_EXTRACTION_SYSTEM = """\
You are a knowledge extraction engine. Your output feeds an AI reasoning system, NOT a human.

Extract every distinct knowledge unit from the transcript. For each unit output a JSON object.

Rules:
- ABSTRACT, do not quote. Rephrase into a clean, standalone statement.
- Each object must be self-contained (no "he", "they", "in this video").
- Prefer precision over completeness. One precise object > two vague ones.
- For procedures: preserve the order. Use a numbered list in content.
- For metrics: always include the number AND what it measures.
- confidence: 1.0 = stated explicitly, 0.7 = strongly implied, 0.4 = inferred.

Output format — JSON array only, no prose:
[
  {
    "type": "<one of: claim|procedure|comparison|constraint|risk|metric|principle|relationship|definition|example>",
    "content": "<abstracted knowledge, max 2 sentences>",
    "entities": ["<entity1>", "<entity2>"],
    "confidence": <0.0-1.0>,
    "timestamp": <approximate seconds into source>
  }
]"""

_VALID_TYPES = set(ALL_TYPES)


def _parse_response(raw: str, video_id: str) -> list[KnowledgeObject]:
    """Parse LLM JSON output into KnowledgeObjects. Tolerant of partial failures."""
    # Strip markdown code fences if present
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip()

    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        # Try to recover a partial array
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return []
        try:
            items = json.loads(match.group())
        except json.JSONDecodeError:
            return []

    objects: list[KnowledgeObject] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        ktype = item.get("type", "")
        if ktype not in _VALID_TYPES:
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        objects.append(
            KnowledgeObject(
                id=f"{video_id}_{i}",
                type=ktype,  # type: ignore[arg-type]
                content=content,
                entities=[str(e) for e in item.get("entities", [])],
                confidence=float(item.get("confidence", 0.8)),
                video_id=video_id,
                timestamp=float(item.get("timestamp", 0.0)),
            )
        )
    return objects


def extract(
    video_id: str,
    compressed_transcript: str,
    verbose: bool = False,
) -> list[KnowledgeObject]:
    """
    Extract knowledge objects from a compressed transcript.
    Single Haiku call — cheap, one-time per video.
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt = (
        f"Extract all knowledge objects from this transcript.\n\n"
        f"Source: YouTube video {video_id}\n\n"
        f"TRANSCRIPT:\n{compressed_transcript}\n\n"
        f"Output the JSON array now:"
    )

    response = client.messages.create(
        model=_HAIKU_MODEL,
        max_tokens=4096,
        system=_EXTRACTION_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text
    objects = _parse_response(raw, video_id)

    if verbose:
        type_counts = {}
        for obj in objects:
            type_counts[obj.type] = type_counts.get(obj.type, 0) + 1
        print(f"[extract] {len(objects)} knowledge objects: {type_counts}")
        cost_usd = (response.usage.input_tokens / 1e6 * 0.25 +
                    response.usage.output_tokens / 1e6 * 1.25)
        print(f"[extract] Haiku cost: ${cost_usd:.4f} (¥{cost_usd*150:.2f})")

    return objects
