"""
Prompt assembly with strict context budget.
Builds a structured prompt from compressed chunks.
"""

from .compression import count_tokens


_SYSTEM = """You are an expert assistant answering questions about YouTube video content.
Answer based ONLY on the provided transcript excerpts. Be concise and precise.
If the answer is not in the excerpts, say so clearly."""

_CONTEXT_HEADER = "## Transcript Excerpts\n"
_CHUNK_TEMPLATE = "[{start:.0f}s–{end:.0f}s] {text}"


def _format_chunk(chunk: dict) -> str:
    meta = chunk.get("meta", {})
    start = meta.get("start", 0)
    end = meta.get("end", start)
    return _CHUNK_TEMPLATE.format(start=start, end=end, text=chunk["text"])


def assemble_prompt(
    chunks: list[dict],
    query: str,
    video_id: str,
    title: str = "",
) -> tuple[str, str]:
    """
    Returns (system_prompt, user_prompt).
    Chunks are sorted by timestamp for readability.
    """
    # Sort by timestamp for natural reading order
    ordered = sorted(chunks, key=lambda c: c.get("meta", {}).get("start", 0))

    context_lines = [_CONTEXT_HEADER]
    if title:
        context_lines.insert(0, f"## Video: {title}\n")

    for chunk in ordered:
        context_lines.append(_format_chunk(chunk))

    context = "\n".join(context_lines)
    user_prompt = f"{context}\n\n## Question\n{query}"

    return _SYSTEM, user_prompt


def estimate_cost(input_tokens: int, output_tokens: int = 500) -> dict:
    """
    Cost estimate for Claude Sonnet 4.6.
    Prices: $3/MTok input, $15/MTok output.
    """
    input_cost = (input_tokens / 1_000_000) * 3.0
    output_cost = (output_tokens / 1_000_000) * 15.0
    total_usd = input_cost + output_cost
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_usd": round(total_usd, 5),
        "total_jpy": round(total_usd * 150, 2),
    }
