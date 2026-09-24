import json

from railtracks.retrieval import (
    ContentExtractor,
    JsonExtractor,
    ProseExtractor,
    StrExtractor,
)


def differently_named_extractor(v: object) -> str:
    return str(v)


def test_protocol_accepts_builtin_and_differently_named_callable() -> None:
    extractors: tuple[ContentExtractor, ...] = (str, differently_named_extractor)
    assert [extractor(42) for extractor in extractors] == ["42", "42"]


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
        "metadata: {reviewed: true; score: null}"
    )


def test_prose_extractor_distinguishes_nested_dicts_from_flat_strings() -> None:
    extractor = ProseExtractor()
    assert extractor({"a": {"b": 1, "c": 2}, "d": 3}) == "a: {b: 1; c: 2}; d: 3"
    assert extractor({"a": {"b": 1, "c": 2}, "d": 3}) != extractor(
        {"a": "b: 1; c: 2", "d": 3}
    )
    assert extractor([{"x": 1}, {"y": 2}]) == "[{x: 1}, {y: 2}]"
