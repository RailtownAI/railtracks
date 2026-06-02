import json

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
