"""
Query parser — determines which knowledge types a query needs.

No LLM. Rule-based signal detection using keyword patterns.
Returns a ranked list of KnowledgeTypes relevant to the query,
so the retriever knows what to prioritize.
"""

import re
from ..knowledge.schema import KnowledgeType

# Keyword → type signals
_SIGNALS: list[tuple[re.Pattern, KnowledgeType, float]] = [
    # Metrics / numbers
    (re.compile(r"\b(how (much|many|fast|accurate|often)|performance|benchmark|score|rate|percent|number|count|speed|cost|price|size)\b", re.I), "metric", 1.0),
    (re.compile(r"\b\d+\b"), "metric", 0.6),

    # Procedures
    (re.compile(r"\b(how to|steps?|process|procedure|method|implement|build|create|set up|install|configure|workflow)\b", re.I), "procedure", 1.0),

    # Comparisons
    (re.compile(r"\b(vs\.?|versus|compare|difference|better|worse|pros?|cons?|advantage|disadvantage|alternative|between)\b", re.I), "comparison", 1.0),

    # Constraints
    (re.compile(r"\b(require[sd]?|requirements?|need[sd]?|prerequisite|limitation|condition|only (works?|when)|must have)\b", re.I), "constraint", 1.0),

    # Risks
    (re.compile(r"\b(risks?|dangers?|fail(ure)?s?|problems?|issues?|bugs?|errors?|warn(ing)?s?|avoid|pitfall|caveat|don.?t|shouldn.?t|careful)\b", re.I), "risk", 1.0),

    # Principles
    (re.compile(r"\b(best practice|rule|principle|always|never|should|recommend|guideline|pattern)\b", re.I), "principle", 1.0),

    # Relationships
    (re.compile(r"\b(relation|connect|depend|enable|cause|affect|impact|between|interaction|role)\b", re.I), "relationship", 0.8),

    # Definitions
    (re.compile(r"\b(what is|what are|define|definition|mean|explain|describe)\b", re.I), "definition", 1.0),

    # Claims (fallback for general factual questions)
    (re.compile(r"\b(why|because|reason|result|consequence|effect|outcome)\b", re.I), "claim", 0.8),
]

# All types as fallback if no signal detected
_DEFAULT_PRIORITY: list[KnowledgeType] = [
    "claim", "principle", "definition", "comparison",
    "metric", "procedure", "constraint", "risk",
    "relationship", "example",
]


def parse_query(query: str) -> list[tuple[KnowledgeType, float]]:
    """
    Returns (type, score) pairs, descending by score.
    Score reflects how likely the query is asking for that knowledge type.
    """
    scores: dict[str, float] = {}
    for pattern, ktype, weight in _SIGNALS:
        matches = pattern.findall(query)
        if matches:
            scores[ktype] = scores.get(ktype, 0.0) + weight * len(matches)

    if not scores:
        # No signal: return all types with equal low priority
        return [(t, 0.1) for t in _DEFAULT_PRIORITY]

    # Always include claim as a baseline (most generic knowledge type)
    if "claim" not in scores:
        scores["claim"] = 0.3

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(t, s) for t, s in ranked]  # type: ignore[misc]


def primary_types(query: str, top_n: int = 4) -> list[KnowledgeType]:
    """Return the top N most relevant knowledge types for a query."""
    return [t for t, _ in parse_query(query)[:top_n]]
