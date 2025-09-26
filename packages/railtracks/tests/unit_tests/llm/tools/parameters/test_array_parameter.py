import pytest
from railtracks.llm.tools.parameters.array_parameter import ArrayParameter
from railtracks.llm.tools.parameters._base import Parameter, ParameterType

class DummyParameter(Parameter):
    param_type = ParameterType.STRING
    def to_json_schema(self):
        return {"type": "string"}

def test_array_parameter_basic():
    arr = ArrayParameter("arr", items=DummyParameter("item"), description="desc", required=False, default=["a"], max_items=3)
    schema = arr.to_json_schema()
    assert schema["type"] == "array"
    assert schema["items"]["type"] == "string"
    assert schema["description"] == "desc"
    assert schema["default"] == ["a"]
    assert schema["maxItems"] == 3

def test_array_parameter_repr():
    arr = ArrayParameter("arr", items=DummyParameter("item"))
    s = repr(arr)
    assert "ArrayParameter" in s
    assert "arr" in s
