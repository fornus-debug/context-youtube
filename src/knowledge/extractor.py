"""
Knowledge extraction — one LLM call per video (not per query).

Provider is selected via LLM_PROVIDER env var (default: anthropic):
  anthropic → Claude Haiku   ~¥1/video
  gemini    → Gemini Flash   無料
  groq      → Llama 3.3 70B  無料

Result cached permanently in SQLite+ChromaDB — zero cost on repeat queries.
"""

import json
import re

from .schema import KnowledgeObject, ALL_TYPES
from ..llm import get_extract_client, provider_label

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
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip()

    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
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
    Single LLM call — one-time per video, result cached permanently.
    """
    client = get_extract_client()

    user = (
        f"Extract all knowledge objects from this transcript.\n\n"
        f"Source: YouTube video {video_id}\n\n"
        f"TRANSCRIPT:\n{compressed_transcript}\n\n"
        f"Output the JSON array now:"
    )

    resp = client.complete(_EXTRACTION_SYSTEM, user, max_tokens=4096)
    objects = _parse_response(resp.text, video_id)

    if verbose:
        type_counts: dict[str, int] = {}
        for obj in objects:
            type_counts[obj.type] = type_counts.get(obj.type, 0) + 1
        label = provider_label()
        cost_jpy = resp.cost_usd * 150
        print(f"[extract] {len(objects)} objects via {label}: "
              f"¥{cost_jpy:.2f} | {type_counts}")

    return objects
