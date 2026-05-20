from src.knowledge.schema import KnowledgeObject, KnowledgeBrief


def _obj(ktype, content, ts=0.0):
    return KnowledgeObject(
        id=f"test_{ktype}",
        type=ktype,
        content=content,
        entities=["entity_a"],
        confidence=0.9,
        video_id="test_video",
        timestamp=ts,
    )


def test_context_line_format():
    obj = _obj("claim", "Machine learning requires large datasets.", 120.0)
    line = obj.to_context_line()
    assert "[120s]" in line
    assert "Machine learning" in line


def test_brief_render_sections():
    brief = KnowledgeBrief(
        video_id="v1",
        query="test",
        objects_by_type={
            "claim": [_obj("claim", "X causes Y", 10.0)],
            "risk":  [_obj("risk", "If you skip X, Y fails", 30.0)],
        },
        total_tokens=50,
    )
    rendered = brief.render()
    assert "Key Claims" in rendered
    assert "Risks" in rendered
    assert "X causes Y" in rendered
    assert "If you skip X" in rendered


def test_brief_render_empty():
    brief = KnowledgeBrief(
        video_id="v1", query="test",
        objects_by_type={}, total_tokens=0
    )
    assert brief.render() == ""


def test_to_dict_roundtrip():
    obj = _obj("metric", "Achieves 94% accuracy on ImageNet.", 60.0)
    d = obj.to_dict()
    assert d["type"] == "metric"
    assert d["confidence"] == 0.9
    assert d["video_id"] == "test_video"
