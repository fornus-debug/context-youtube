from src.compiler.ranker import rank, score
from src.knowledge.schema import KnowledgeObject


def _obj(ktype, content, confidence=0.9, ts=0.0):
    return KnowledgeObject(
        id=f"test_{ktype}_{ts}",
        type=ktype,
        content=content,
        entities=["machine learning", "neural network"],
        confidence=confidence,
        video_id="v1",
        timestamp=ts,
    )


def test_rank_sorts_descending():
    candidates = [
        (_obj("claim", "X causes Y"), 0.5),
        (_obj("risk", "Y fails if X missing"), 0.9),
        (_obj("metric", "Achieves 94% accuracy"), 0.3),
    ]
    ranked = rank(candidates, "what are the risks?", ["risk"], total_duration=300)
    scores = [s for _, s in ranked]
    assert scores == sorted(scores, reverse=True)


def test_priority_type_scores_higher():
    obj_priority = _obj("risk", "Overfitting causes poor generalization", 0.8)
    obj_other = _obj("example", "MNIST is a common benchmark", 0.8)

    score_priority = score(obj_priority, 0.7, "what are the risks?", ["risk"])
    score_other = score(obj_other, 0.7, "what are the risks?", ["risk"])
    assert score_priority > score_other


def test_confidence_affects_score():
    obj_high = _obj("claim", "Learning rate affects convergence", confidence=0.95)
    obj_low = _obj("claim", "Learning rate affects convergence", confidence=0.3)

    s_high = score(obj_high, 0.7, "learning rate", ["claim"])
    s_low = score(obj_low, 0.7, "learning rate", ["claim"])
    assert s_high > s_low


def test_rank_empty_input():
    assert rank([], "query", ["claim"]) == []


def test_entity_overlap_boosts_score():
    obj_match = _obj("claim", "Neural networks learn features", 0.8)
    obj_match.entities = ["neural networks", "features"]

    obj_no_match = _obj("claim", "Statistics are important", 0.8)
    obj_no_match.entities = ["statistics"]

    s1 = score(obj_match, 0.7, "how do neural networks work?", ["claim"])
    s2 = score(obj_no_match, 0.7, "how do neural networks work?", ["claim"])
    assert s1 > s2
