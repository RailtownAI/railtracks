import pytest
from railtracks.llm.tools.parameters.union_parameter import UnionParameter
from railtracks.llm.tools.parameters._base import Parameter, ParameterType

def make_dummy_param(name, param_type):
    class Dummy(Parameter):
        def to_json_schema(self):
            return {"type": param_type}
    return Dummy(name, param_type=param_type)

def test_union_parameter_basic():
    p1 = make_dummy_param("foo", "string")
    p2 = make_dummy_param("bar", "integer")
    union = UnionParameter("baz", options=[p1, p2], description="desc", required=True, default_present=True, default=123)
    schema = union.to_json_schema()
    assert "anyOf" in schema
    assert {"type": "string"} in schema["anyOf"]
    assert {"type": "integer"} in schema["anyOf"]
    assert schema["description"] == "desc"
    assert schema["default"] == 123

def test_union_parameter_no_nested_union():
    p1 = make_dummy_param("foo", "string")
    with pytest.raises(TypeError):
        UnionParameter("baz", options=[p1, UnionParameter("bad", options=[p1])])

def test_union_parameter_repr():
    p1 = make_dummy_param("foo", "string")
    p2 = make_dummy_param("bar", "integer")
    union = UnionParameter("baz", options=[p1, p2])
    s = repr(union)
    assert "UnionParameter" in s
    assert "baz" in s
