import json
import pytest
from railtracks.state import serialize


# ================= START encoder_extender tests ==================

@pytest.mark.parametrize(
    "fixture_name,expected_keys,encode_func,expected_type",
    [
        ("fake_edge", {"source", "target", "identifier", "stamp", "details", "parent"}, serialize.encode_edge, dict),
        ("fake_vertex", {"identifier", "node_type", "name", "stamp", "details", "parent"}, serialize.encode_vertex, dict),
        ("fake_stamp", {"step", "time", "identifier"}, serialize.encode_stamp, dict),
        ("fake_request_details", {"model_name", "model_provider", "input", "output", "input_tokens", "output_tokens", "total_cost", "system_fingerprint", "latency"}, serialize.encode_request_details, dict),
        ("fake_message", {"role", "content"}, serialize.encode_message, dict),
        ("fake_tool_response", {"identifier", "name", "result"}, serialize.encode_content, dict),
        ("fake_tool_call", {"identifier", "name", "arguments"}, serialize.encode_tool_call, dict),
        ("fake_latency_details", {"total_time"}, serialize.encode_latency_details, dict),
        ("fake_basemodel", {"hello"}, serialize.encode_base_model, dict),
    ]
)
def test_encoder_extension_encodes_types_correctly(request, fixture_name, expected_keys, encode_func, expected_type):
    obj = request.getfixturevalue(fixture_name)
    d = encode_func(obj)
    assert isinstance(d, expected_type)
    assert set(d.keys()).issuperset(expected_keys)

def test_encoder_extender_raises_on_unknown():
    class Unk: pass
    with pytest.raises(TypeError):
        serialize.encoder_extender(Unk())

# =============== END encoder_extender tests ======================

# =============== START RTJSONEncoder tests =======================

@pytest.mark.parametrize(
    "fixture_name",
    [
        "fake_edge", "fake_vertex", "fake_stamp", "fake_request_details",
        "fake_message", "fake_tool_response", "fake_tool_call",
        "fake_latency_details", "fake_basemodel",
    ]
)
def test_rtjsonencoder_supports_all_supported_types(request, fixture_name):
    o = request.getfixturevalue(fixture_name)
    # Should not raise and should return a JSON string
    s = json.dumps(o, cls=serialize.RTJSONEncoder)
    assert isinstance(s, str)
    assert s.startswith("{") or s.startswith("\"")  # top-level obj or string

def test_rtjsonencoder_fallback_on_unknown_type():
    # Forces fallback to string representation
    class Unk:
        pass
    class DummyEnc(serialize.RTJSONEncoder):
        def default(self, o):
            return super().default(o)
    to_enc = Unk()
    enc = DummyEnc()
    val = enc.default(to_enc)
    assert "ERROR:" in str(val)

# =============== END RTJSONEncoder tests =========================