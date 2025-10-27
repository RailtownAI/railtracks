import pytest
from railtracks.llm.tools.parameters.object_parameter import ObjectParameter
from railtracks.llm.tools.parameters._base import Parameter, ParameterType

class DummyParameter(Parameter):
    param_type = ParameterType.STRING
    def to_json_schema(self):
        return {"type": "string"}

def test_object_parameter_basic():
    obj = ObjectParameter(
        "obj",
        properties=[DummyParameter("foo", required=True), DummyParameter("bar", required=False)],
        description="desc",
        required=True,
        additional_properties=True,
        default=None,
    )
    schema = obj.to_json_schema()
    assert schema["type"] == "object"
    assert "foo" in schema["properties"]
    assert schema["properties"]["foo"]["type"] == "string"
    assert schema["description"] == "desc"
    assert schema["additionalProperties"] is True
    assert "required" in schema and "foo" in schema["required"]

def test_object_parameter_repr():
    obj = ObjectParameter("obj", properties=[])
    s = repr(obj)
    assert "ObjectParameter" in s
    assert "obj" in s
