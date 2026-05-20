"""
Context brief assembler.

Takes ranked KnowledgeObjects and builds a structured brief
optimized for LLM reasoning — typed sections, not raw text.

Budget enforcement: token estimation with hard cutoff.
Type ordering: most query-relevant types come first.
"""

import os
from ..knowledge.schema import KnowledgeObject, KnowledgeBrief, KnowledgeType

_BUDGET = int(os.getenv("CONTEXT_BUDGET_TOKENS", "6000"))


def _approx_tokens(text: str) -> int:
    return int(len(text.split()) * 1.35)


def assemble(
    ranked: list[tuple[KnowledgeObject, float]],
    query: str,
    video_id: str,
    priority_types: list[KnowledgeType],
    budget_tokens: int = _BUDGET,
) -> KnowledgeBrief:
    """
    Build a KnowledgeBrief from ranked knowledge objects within token budget.

    Allocation strategy:
      1. Priority types get 60% of the budget
      2. Remaining types share 40%
      3. Within each type: highest-scored objects first
    """
    priority_set = set(priority_types)
    priority_budget = int(budget_tokens * 0.60)
    remainder_budget = budget_tokens - priority_budget

    objects_by_type: dict[str, list[KnowledgeObject]] = {}
    used_priority = 0
    used_remainder = 0

    for obj, _score in ranked:
        ktype = obj.type
        line = obj.to_context_line()
        tokens = _approx_tokens(line)

        if ktype in priority_set:
            if used_priority + tokens > priority_budget:
                continue
            used_priority += tokens
        else:
            if used_remainder + tokens > remainder_budget:
                continue
            used_remainder += tokens

        if ktype not in objects_by_type:
            objects_by_type[ktype] = []
        objects_by_type[ktype].append(obj)

    total_tokens = _approx_tokens(
        "\n".join(
            obj.to_context_line()
            for objs in objects_by_type.values()
            for obj in objs
        )
    )

    return KnowledgeBrief(
        video_id=video_id,
        query=query,
        objects_by_type=objects_by_type,
        total_tokens=total_tokens,
    )


_SYSTEM = """\
You are an expert analyst answering questions using structured knowledge extracted from a video.
The knowledge below is pre-structured by type (Claims, Metrics, Risks, etc.).
Answer based ONLY on the provided knowledge objects.
Be precise. Reference timestamps when relevant.
If the answer is not in the knowledge base, say so."""


def build_prompt(brief: KnowledgeBrief, title: str = "") -> tuple[str, str]:
    """Returns (system_prompt, user_prompt)."""
    header = f"# Knowledge Base: {title or brief.video_id}\n" if title else ""
    user = f"{header}{brief.render()}\n\n## Question\n{brief.query}"
    return _SYSTEM, user
