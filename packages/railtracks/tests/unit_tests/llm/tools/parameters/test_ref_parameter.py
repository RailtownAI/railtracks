import pytest
from railtracks.llm.tools.parameters.ref_parameter import RefParameter

def test_ref_parameter_basic():
    ref = RefParameter("foo", ref_path="#/$defs/Bar", description="desc", required=False, default=None)
    schema = ref.to_json_schema()
    assert schema["$ref"] == "#/$defs/Bar"
    assert schema["description"] == "desc"

def test_ref_parameter_repr():
    ref = RefParameter("foo", ref_path="#/$defs/Bar")
    s = repr(ref)
    assert "RefParameter" in s
    assert "foo" in s
    assert "#/$defs/Bar" in s
