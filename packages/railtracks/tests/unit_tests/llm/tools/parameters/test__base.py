import json
from dataclasses import dataclass
from typing import TypedDict

import pytest
from railtracks.llm.tools.parameters._base import Parameter, ParameterType


class ExampleTypedDict(TypedDict):
    field: str


@dataclass
class ExampleDataclass:
    field: str


def test_parameter_init_and_repr():
    p = Parameter("foo", description="desc", required=False, default="bar", enum=["bar", "baz"])
    assert p.name == "foo"
    assert p.description == "desc"
    assert not p.required
    assert p.default == "bar"
    assert p.enum == ["bar", "baz"]

def test_parameter_to_json_schema():
    p = Parameter("foo", param_type="string", description="desc", required=True, default="bar", enum=["bar", "baz"], default_present=True)
    schema = p.to_json_schema()
    assert schema["type"] == "string"
    assert schema["description"] == "desc"
    assert schema["enum"] == ["bar", "baz"]
    assert schema["default"] == "bar"

def test_param_type_from_python_type():
    assert ParameterType.from_python_type(str) == ParameterType.STRING
    assert ParameterType.from_python_type(int) == ParameterType.INTEGER
    assert ParameterType.from_python_type(float) == ParameterType.FLOAT
    assert ParameterType.from_python_type(bool) == ParameterType.BOOLEAN
    assert ParameterType.from_python_type(list) == ParameterType.ARRAY
    assert ParameterType.from_python_type(dict) == ParameterType.OBJECT
    assert ParameterType.from_python_type(type(None)) == ParameterType.NONE


def test_parameter_accepts_python_type_str():
    p = Parameter("query", description="The search query string.", param_type=str)
    assert p.param_type == "string"
    assert p.to_json_schema()["type"] == "string"
    json.dumps(p.to_json_schema())


def test_parameter_accepts_python_type_int():
    p = Parameter("n", description="A number.", param_type=int)
    assert p.param_type == "integer"
    assert p.to_json_schema()["type"] == "integer"
    json.dumps(p.to_json_schema())


def test_parameter_list_accepts_mixed_python_and_schema_types():
    p = Parameter("x", param_type=[str, "null"])
    assert p.param_type == ["string", "null"]


def test_parameter_normalizes_none_alias():
    p = Parameter("x", param_type="none")
    assert p.param_type == "null"


@pytest.mark.parametrize("param_type", ["bool", ["string", "bool"]])
def test_parameter_rejects_invalid_json_schema_type(param_type):
    with pytest.raises(
        ValueError,
        match="Invalid param_type 'bool' provided for parameter 'enabled'",
    ):
        Parameter("enabled", param_type=param_type)


@pytest.mark.parametrize("py_type", [bytes, ExampleTypedDict, ExampleDataclass])
def test_parameter_maps_unmodelled_python_type_to_object(py_type):
    """Types we cannot describe more precisely still serialize as 'object'."""
    p = Parameter("payload", param_type=py_type)
    assert p.param_type == "object"


@pytest.mark.parametrize(
    "schema_type",
    ["string", "integer", "number", "boolean", "array", "object", "null"],
)
def test_from_python_type_passes_through_schema_type_names(schema_type):
    """A resolved schema type name must survive, not collapse to 'object'."""
    assert ParameterType.from_python_type(schema_type).value == schema_type


@pytest.mark.parametrize(
    "annotation, expected",
    [
        ("str", "string"),
        ("int", "integer"),
        ("float", "number"),
        ("bool", "boolean"),
        ("list", "array"),
        ("tuple", "array"),
        ("set", "array"),
        ("dict", "object"),
        ("NoneType", "null"),
        ("none", "null"),
    ],
)
def test_from_python_type_resolves_postponed_annotations(annotation, expected):
    """`from __future__ import annotations` makes signatures yield type names as strings."""
    assert ParameterType.from_python_type(annotation).value == expected


@pytest.mark.parametrize("annotation", ["TodoState", "list[str]", "Any"])
def test_from_python_type_falls_back_to_object_for_unresolved_annotations(annotation):
    assert ParameterType.from_python_type(annotation) is ParameterType.OBJECT
