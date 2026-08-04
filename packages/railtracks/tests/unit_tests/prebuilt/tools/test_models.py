"""Tests for prebuilt/tools/websearch/models.py — SearchResult, FetchResult."""

import pytest
from pydantic import ValidationError
from railtracks.prebuilt.tools.websearch.models import FetchResult, SearchResult


def test_search_result_requires_fields():
    result = SearchResult(title="t", url="u", snippet="s")
    assert result.title == "t"
    assert result.url == "u"
    assert result.snippet == "s"


def test_search_result_missing_field_raises():
    with pytest.raises(ValidationError):
        SearchResult(title="t", url="u")


def test_fetch_result_defaults():
    result = FetchResult(url="u")
    assert result.title is None
    assert result.text == ""
    assert result.is_error is False
    assert result.error_message is None


def test_fetch_result_error_only():
    result = FetchResult(url="u", is_error=True, error_message="nope")
    assert result.is_error is True
    assert result.error_message == "nope"
    assert result.text == ""
