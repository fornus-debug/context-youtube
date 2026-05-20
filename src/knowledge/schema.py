"""
Knowledge object schema — the atomic unit of this system.

Text chunks are NOT the unit of storage. KnowledgeObjects are.
Each object is an abstraction of something the source said,
typed by its epistemic role, optimized for AI consumption.
"""

from dataclasses import dataclass, field
from typing import Literal

KnowledgeType = Literal[
    "claim",        # X is / does / causes Y  (factual assertion)
    "procedure",    # ordered steps to accomplish X
    "comparison",   # X vs Y across dimension Z
    "constraint",   # X only works when / requires Y
    "risk",         # if X then negative consequence Y
    "metric",       # X achieves N (quantified fact)
    "principle",    # always / never / prefer X over Y (rule)
    "relationship", # X enables / blocks / depends on Y
    "definition",   # X is defined as Y
    "example",      # X illustrates Y in context Z
]

ALL_TYPES: tuple[KnowledgeType, ...] = (
    "claim", "procedure", "comparison", "constraint",
    "risk", "metric", "principle", "relationship",
    "definition", "example",
)


@dataclass
class KnowledgeObject:
    id: str                         # "{video_id}_{index}"
    type: KnowledgeType
    content: str                    # abstracted, compressed, standalone
    entities: list[str]             # key concepts / nouns involved
    confidence: float               # 0.0–1.0
    video_id: str
    timestamp: float                # seconds into video
    embedding: list[float] = field(default_factory=list, repr=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "entities": self.entities,
            "confidence": self.confidence,
            "video_id": self.video_id,
            "timestamp": self.timestamp,
        }

    def to_context_line(self) -> str:
        """Single-line representation for context brief assembly."""
        ts = f"[{int(self.timestamp)}s]"
        return f"{ts} {self.content}"


@dataclass
class KnowledgeBrief:
    """
    Structured context sent to the final LLM.
    Typed by knowledge category — NOT raw text.
    """
    video_id: str
    query: str
    objects_by_type: dict[str, list[KnowledgeObject]]
    total_tokens: int

    def render(self) -> str:
        """Render a structured brief optimized for LLM reasoning."""
        sections = []
        type_labels = {
            "claim":        "## Key Claims",
            "procedure":    "## Procedures / Steps",
            "comparison":   "## Comparisons",
            "constraint":   "## Constraints & Preconditions",
            "risk":         "## Risks & Failure Modes",
            "metric":       "## Metrics & Numbers",
            "principle":    "## Principles & Rules",
            "relationship": "## Relationships",
            "definition":   "## Definitions",
            "example":      "## Examples",
        }
        for ktype, label in type_labels.items():
            objs = self.objects_by_type.get(ktype, [])
            if not objs:
                continue
            lines = [label]
            for obj in objs:
                lines.append(f"- {obj.to_context_line()}")
            sections.append("\n".join(lines))
        return "\n\n".join(sections)
