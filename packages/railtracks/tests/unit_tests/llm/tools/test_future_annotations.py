from __future__ import annotations

import enum
import json
import warnings
from typing import List, Literal, Optional

import pytest
import railtracks as rt
from railtracks.exceptions import NodeCreationError
from railtracks.llm.tools.parameters import Parameter, ParameterType
from railtracks.llm.tools.tool import Tool
from railtracks.validation.node_creation.validation import (
    validate_tool_manifest_against_function,
)


class Color(enum.Enum):
    RED = "red"


class StrColor(str, enum.Enum):
    RED = "red"


def paint(c: Literal[Color.RED]) -> None:
    pass


def paint_str(c: Literal[StrColor.RED]) -> None:
    pass


def lookup(pattern: str, amount: Undefined) -> str:  # noqa: F821
    return ""


def count(n: int) -> None:
    pass


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

    assert mode_param.param_type == ParameterType.STRING.value
    assert mode_param.enum == ["fast", "slow"]


def test_non_primitive_literal_falls_back_to_object():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        tool = Tool.from_function(paint)
        schema = tool.encode()["parameters"][0].to_json_schema()
        assert schema["type"] == "object"
        assert "enum" not in schema
        assert json.loads(json.dumps(schema)) == schema


def test_str_enum_literal_keeps_its_values():
    tool = Tool.from_function(paint_str)
    schema = tool.encode()["parameters"][0].to_json_schema()
    assert json.loads(json.dumps(schema)) == {"type": "string", "enum": ["red"]}


def test_manifest_skips_annotation_resolution_warning():
    manifest = rt.ToolManifest(
        "Look something up.",
        [
            Parameter(name="pattern", param_type="string", required=True),
            Parameter(name="amount", param_type="number", required=True),
        ],
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        node = rt.function_node(lookup, manifest=manifest)
        params = node.node_type.tool_info().parameters
        assert {p.name: p.param_type for p in params} == {
            "pattern": "string",
            "amount": "number",
        }


def test_unresolvable_annotation_still_warns_without_manifest():
    with pytest.warns(UserWarning, match="Could not resolve type annotations"):
        rt.function_node(lookup)


def test_manifest_mismatch_against_resolved_type_still_raises():
    with pytest.raises(NodeCreationError, match="Type mismatch"):
        validate_tool_manifest_against_function(
            count, [Parameter(name="n", param_type="string", required=True)]
        )


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
