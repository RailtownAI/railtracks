from __future__ import annotations

from typing import List, Literal, Optional

from railtracks.llm.tools.parameters import ParameterType
from railtracks.llm.tools.tool import Tool


def search_files(pattern: str, limit: int = 10) -> str:
    """Search files.

    Args:
        pattern: Regex to search for.
        limit: Max results.
    """
    return ""


def process_items(
    mode: Literal["fast", "slow"],
    items: List[str] | None = None,
    count: Optional[int] = None,
):
    pass


def test_tool_from_function_with_future_annotations():
    tool = Tool.from_function(search_files)
    schema = tool.encode()

    parameters = schema.get("parameters", [])

    pattern_param = next(p for p in parameters if p.name == "pattern")
    limit_param = next(p for p in parameters if p.name == "limit")

    assert pattern_param.param_type == ParameterType.STRING.value
    assert limit_param.param_type == ParameterType.INTEGER.value


def test_tool_from_function_literal_and_union():
    tool = Tool.from_function(process_items)
    schema = tool.encode()

    parameters = schema.get("parameters", [])

    mode_param = next(p for p in parameters if p.name == "mode")
    items_param = next(p for p in parameters if p.name == "items")
    count_param = next(p for p in parameters if p.name == "count")

    assert mode_param.param_type == ParameterType.STRING.value
    assert mode_param.enum == ["fast", "slow"]

    assert items_param.to_json_schema() == {"anyOf": [{"type": "object"}]}

    assert count_param.to_json_schema() == {"anyOf": [{"type": "integer"}]}


def test_type_checking_warning():
    import warnings

    def hidden_import_func(param: "UnknownType"):  # noqa: F821
        pass

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        tool = Tool.from_function(hidden_import_func)
        assert len(w) == 1
        assert "Could not resolve type annotations" in str(w[-1].message)

    schema = tool.encode()
    param = schema["parameters"][0]
    assert param.to_json_schema() == {"type": "object"}


def test_manifest_literal_accepted():
    from railtracks.llm.tools.parameters import Parameter
    from railtracks.validation.node_creation.validation import (
        validate_tool_manifest_against_function,
    )

    def my_func(mode: Literal["fast", "slow"]):
        pass

    # Manifest accepts "string" for a Literal parameter
    manifest_params = [Parameter(name="mode", param_type="string", required=True)]

    # Should not raise any NodeCreationError
    validate_tool_manifest_against_function(my_func, manifest_params)


def test_mixed_literal():
    def my_mixed_func(mode: Literal[True, 1, "test"]):
        pass

    tool = Tool.from_function(my_mixed_func)
    schema = tool.encode()

    mode_param = schema["parameters"][0]
    json_schema = mode_param.to_json_schema()

    # Types should be a list containing boolean, integer, string
    assert isinstance(json_schema["type"], list)
    assert sorted(json_schema["type"]) == ["boolean", "integer", "string"]
    assert json_schema["enum"] == [True, 1, "test"]
