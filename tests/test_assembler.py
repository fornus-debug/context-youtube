from src.compiler.assembler import assemble, build_prompt
from src.knowledge.schema import KnowledgeObject


def _obj(ktype, content, ts=0.0, conf=0.9):
    return KnowledgeObject(
        id=f"{ktype}_{ts}",
        type=ktype,
        content=content,
        entities=["test"],
        confidence=conf,
        video_id="v1",
        timestamp=ts,
    )


def _ranked(objects, base_score=0.8):
    return [(obj, base_score - i * 0.05) for i, obj in enumerate(objects)]


def test_assemble_respects_budget():
    # Create many objects that would exceed budget
    objects = [_obj("claim", "word " * 50, ts=float(i)) for i in range(30)]
    ranked = _ranked(objects)
    brief = assemble(ranked, "test query", "v1", ["claim"], budget_tokens=200)
    assert brief.total_tokens <= 250  # small tolerance


def test_assemble_priority_types_included():
    objects = [
        _obj("claim", "X causes Y", ts=0),
        _obj("risk", "Y fails when X missing", ts=10),
        _obj("example", "MNIST is a benchmark", ts=20),
    ]
    ranked = _ranked(objects)
    brief = assemble(ranked, "what are the risks?", "v1", ["risk"])
    # Risk (priority type) should be in the brief
    assert "risk" in brief.objects_by_type


def test_assemble_empty_ranked():
    brief = assemble([], "query", "v1", ["claim"])
    assert brief.objects_by_type == {}
    assert brief.total_tokens == 0


def test_build_prompt_structure():
    objects = [_obj("claim", "Machine learning requires data", ts=30)]
    ranked = _ranked(objects)
    brief = assemble(ranked, "what is ML?", "v1", ["claim", "definition"])
    system, user = build_prompt(brief, "Test Video")
    assert "structured" in system.lower() or "knowledge" in system.lower()
    assert "what is ML?" in user
    assert "Test Video" in user


def test_build_prompt_contains_typed_sections():
    objects = [
        _obj("claim", "Gradient descent minimizes loss", ts=10),
        _obj("metric", "Achieves 0.001 loss on training set", ts=20),
    ]
    ranked = _ranked(objects)
    brief = assemble(ranked, "performance?", "v1", ["metric", "claim"])
    _, user = build_prompt(brief)
    # Should have type section headers
    assert "Claims" in user or "Metrics" in user
