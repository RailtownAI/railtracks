import json

import pytest
from railtracks.llm.tools.parameters._base import Parameter, ParameterType


def test_parameter_init_and_repr():
    p = Parameter(
        "foo", description="desc", required=False, default="bar", enum=["bar", "baz"]
    )
    assert p.name == "foo"
    assert p.description == "desc"
    assert not p.required
    assert p.default == "bar"
    assert p.enum == ["bar", "baz"]


def test_parameter_to_json_schema():
    p = Parameter(
        "foo",
        param_type="string",
        description="desc",
        required=True,
        default="bar",
        enum=["bar", "baz"],
        default_present=True,
    )
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


def test_param_type_from_python_type_unrecognized_type():
    # Verify graceful fallback to OBJECT for unannotated/unrecognized types
    assert ParameterType.from_python_type(bytes) == ParameterType.OBJECT


def test_explicit_param_type_strictly_rejects_unrecognized_string():
    # Verify that explicit unrecognized string types are strictly rejected
    with pytest.raises(ValueError, match="Unrecognized schema parameter type"):
        Parameter("foo", param_type="invalid_schema_type")


def test_explicit_param_type_strictly_rejects_unmapped_python_type():
    # Verify that explicit unmapped python types are strictly rejected
    with pytest.raises(ValueError, match="Unmapped Python type"):
        Parameter("foo", param_type=bytes)


def test_explicit_param_type_none_alias_resolves_to_null():
    # Verify that 'none' is accepted and resolves to 'null'
    p = Parameter("foo", param_type="none")
    assert p.param_type == "null"


def test_nullable_union_resolves_correctly():
    # Verify ["string", "null"] / Optional[str] equivalent resolves cleanly
    p = Parameter("foo", param_type=["string", "null"])
    assert p.param_type == ["string", "null"]


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


def test_to_json_schema_default_injection_with_none():
    # Repro case from Maintainer: ensure 'none' in a list is normalized to 'null'
    # and default=None is correctly injected
    p = Parameter("foo", param_type=["string", "none"])
    schema = p.to_json_schema()
    assert schema == {"type": ["string", "null"], "default": None}
