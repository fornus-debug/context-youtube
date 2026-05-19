from src.compiler.query_parser import parse_query, primary_types


def test_metric_query():
    types = primary_types("how fast is the inference speed?")
    assert "metric" in types


def test_procedure_query():
    types = primary_types("how to implement gradient descent step by step?")
    assert "procedure" in types


def test_comparison_query():
    types = primary_types("what is the difference between Adam and SGD?")
    assert "comparison" in types


def test_risk_query():
    types = primary_types("what are the risks of overfitting?")
    assert "risk" in types


def test_definition_query():
    types = primary_types("what is attention mechanism?")
    assert "definition" in types


def test_constraint_query():
    types = primary_types("what are the requirements for this approach to work?")
    assert "constraint" in types


def test_generic_query_returns_claim():
    types = primary_types("tell me about this video")
    assert "claim" in types


def test_parse_query_returns_scores():
    results = parse_query("how many parameters does GPT-4 have?")
    assert len(results) > 0
    scores = [s for _, s in results]
    assert scores == sorted(scores, reverse=True)


def test_primary_types_top_n():
    types = primary_types("what is the best practice?", top_n=3)
    assert len(types) <= 3
