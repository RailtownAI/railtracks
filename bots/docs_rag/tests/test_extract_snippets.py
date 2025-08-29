import os
import pytest

from bots.docs_rag.extract_snippets import extract_snippets

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(TESTS_DIR)))
SAMPLE_SCRIPT = os.path.join(TESTS_DIR, "sample_script.py")

# Inline markdown/text content for tests
ADD_FN_MD = '--8<-- "bots/docs_rag/tests/sample_script.py:add_fn"'
MULTIPLY_FN_MD = '--8<-- "bots/docs_rag/tests/sample_script.py:multiply_fn"'
BLOCK_FN_MD = '--8<-- "bots/docs_rag/tests/sample_script.py:block_fn"'
INNER_SNIPPET_MD = '--8<-- "bots/docs_rag/tests/sample_script.py:inner"'
LINE_RANGE_MD = '--8<-- "bots/docs_rag/tests/sample_script.py:5:6"'
MULTI_RANGE_MD = '--8<-- "bots/docs_rag/tests/sample_script.py:5:6,10:11"'
SKIPPED_FILE_MD = '--8<-- ";bots/docs_rag/tests/should_not_exist.py:add_fn"'
NO_EXTRA_MD = '--8<-- "bots/docs_rag/tests/sample_script.py:comment_fn"'
INVALID_PATTERN_MD = "--8<-- 'invalid_pattern'"


def test_add_fn_extraction():
    result = extract_snippets(ADD_FN_MD, WORKSPACE_ROOT)
    assert "def add(a, b):\n    return a + b" in result

def test_multiply_fn_extraction():
    result = extract_snippets(MULTIPLY_FN_MD, WORKSPACE_ROOT)
    assert "def multiply(a, b):\n    return a * b" in result

def test_block_fn_extraction():
    result = extract_snippets(BLOCK_FN_MD, WORKSPACE_ROOT)
    assert "def block():\n    x = 1\n    y = 2\n    return x + y" in result

def test_inner_named_snippet():
    result = extract_snippets(INNER_SNIPPET_MD, WORKSPACE_ROOT)
    assert "def inner():\n    pass" in result

def test_line_range_extraction():
    result = extract_snippets(LINE_RANGE_MD, WORKSPACE_ROOT)
    assert "def add(a, b):\n    return a + b" in result

def test_multi_range_extraction():
    result = extract_snippets(MULTI_RANGE_MD, WORKSPACE_ROOT)
    assert "def add(a, b):\n    return a + b" in result
    assert "def multiply(a, b):\n    return a * b" in result

def test_skipped_file():
    result = extract_snippets(SKIPPED_FILE_MD, WORKSPACE_ROOT)
    assert "should_not_exist" not in result

def test_no_extra_characters():
    result = extract_snippets(NO_EXTRA_MD, WORKSPACE_ROOT)
    assert "--8<--" not in result
