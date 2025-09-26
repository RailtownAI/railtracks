import pytest
from railtracks.llm.tools.parameters._base import Parameter, ParameterType


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
