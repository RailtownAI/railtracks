import json

from railtracks.retrieval import JsonExtractor, ProseExtractor, StrExtractor


def test_str_extractor_preserves_python_string_conversion() -> None:
    value = {"answer": None, "verified": True}

    assert StrExtractor()(value) == str(value)


def test_json_extractor_returns_valid_unicode_json() -> None:
    value = {"city": "München", "active": True, "score": None}

    rendered = JsonExtractor()(value)

    assert json.loads(rendered) == value
    assert "München" in rendered


def test_prose_extractor_flattens_nested_json_values() -> None:
    value = {
        "text": "What is retrieval?",
        "tokens": ["What", "is", "retrieval"],
        "metadata": {"reviewed": True, "score": None},
    }

    assert ProseExtractor()(value) == (
        "text: What is retrieval?; tokens: [What, is, retrieval]; "
        "metadata: reviewed: true; score: null"
    )
