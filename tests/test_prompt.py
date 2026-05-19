from src.prompt import assemble_prompt, estimate_cost


def _make_chunks(n: int = 3) -> list[dict]:
    return [
        {
            "text": f"Chunk {i} with some content about the topic.",
            "meta": {"start": float(i * 30), "end": float(i * 30 + 29)},
            "attention_score": 1.0 / (i + 1),
            "tokens": 10,
        }
        for i in range(n)
    ]


def test_assemble_prompt_structure():
    chunks = _make_chunks(3)
    system, user = assemble_prompt(chunks, "What is the main topic?", "vid123", "Test Video")
    assert "transcript" in system.lower() or "assistant" in system.lower()
    assert "What is the main topic?" in user
    assert "Test Video" in user
    assert "0s" in user or "30s" in user  # timestamps present


def test_assemble_sorted_by_time():
    chunks = [
        {"text": "later content", "meta": {"start": 60.0, "end": 90.0}, "tokens": 5},
        {"text": "earlier content", "meta": {"start": 0.0, "end": 30.0}, "tokens": 5},
    ]
    _, user = assemble_prompt(chunks, "test query", "vid")
    earlier_pos = user.find("earlier content")
    later_pos = user.find("later content")
    assert earlier_pos < later_pos


def test_estimate_cost_structure():
    cost = estimate_cost(5000, 500)
    assert "total_usd" in cost
    assert "total_jpy" in cost
    assert cost["total_jpy"] > 0
    assert cost["input_tokens"] == 5000


def test_estimate_cost_reasonable():
    # 6000 input + 500 output should be well under ¥5
    cost = estimate_cost(6000, 500)
    assert cost["total_jpy"] < 5.0
