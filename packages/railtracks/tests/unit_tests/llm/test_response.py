from railtracks.llm.response import Response, MessageInfo
from railtracks.llm import AssistantMessage, UserMessage
import pytest

# ================= START message_info tests ============

def test_message_info_total_tokens_with_both_tokens():
    mi = MessageInfo(input_tokens=3, output_tokens=4)
    assert mi.total_tokens == 7


def test_message_info_total_tokens_none_when_missing_tokens():
    mi1 = MessageInfo(input_tokens=None, output_tokens=5)
    assert mi1.total_tokens is None

    mi2 = MessageInfo(input_tokens=2, output_tokens=None)
    assert mi2.total_tokens is None


def test_message_info_repr_contains_fields():
    mi = MessageInfo(
        input_tokens=1,
        output_tokens=2,
        latency=0.5,
        model_name="test-model",
        total_cost=0.01,
        system_fingerprint="fp123",
    )
    r = repr(mi)
    assert "MessageInfo(" in r
    assert "input_tokens=1" in r
    assert "output_tokens=2" in r
    assert "latency=0.5" in r
    assert "model_name='test-model'" or "model_name=test-model" in r
    assert "total_cost=0.01" in r
    assert "system_fingerprint='fp123'" or "system_fingerprint=fp123" in r

# ================ END message_info tests ===============


# ================= START response tests ============
def test_response_str_uses_message_str_when_present():
    message = AssistantMessage("Hello there.")
    resp = Response(message=message)
    assert str(resp) == str(message)


def test_response_repr_includes_components():
    mi = MessageInfo(input_tokens=1, output_tokens=2)
    message = AssistantMessage("Hi")
    resp = Response(message=message, message_info=mi)
    s = repr(resp)
    assert "Response(" in s
    assert "message=" in s
    assert "message_info=" in s


def test_response_message():
    message = AssistantMessage("Streaming test.")
    resp = Response(message=message)
    assert resp.message is message
    assert resp is not None


def test_response_invalid_message_type_raises_type_error():
    with pytest.raises(TypeError):
        Response(123)



def test_response_message_info_assigned_and_accessible():
    mi = MessageInfo(input_tokens=5, output_tokens=7, latency=0.12, model_name="test-model", total_cost=0.5)
    message = AssistantMessage("Info test.")
    resp = Response(message=message, message_info=mi)
    assert resp.message_info is mi
    assert resp.message_info.input_tokens == 5
    assert resp.message_info.output_tokens == 7
    assert resp.message_info.latency == 0.12
    assert resp.message_info.model_name == "test-model"
    assert resp.message_info.total_cost == 0.5


def test_response_default_message_info_is_used_when_not_provided():
    resp = Response(message=AssistantMessage("Default info test."))
    # Ensure we have a MessageInfo object and its fields are None by default
    mi = resp.message_info
    assert isinstance(mi, MessageInfo)
    assert mi.input_tokens is None
    assert mi.output_tokens is None
    assert mi.latency is None
    assert mi.model_name is None
    assert mi.total_cost is None
    assert mi.system_fingerprint is None


def test_response_message_info_is_same_object_when_passed():
    mi = MessageInfo(input_tokens=2, output_tokens=3)
    resp = Response(message=AssistantMessage("Check"), message_info=mi)
    assert resp.message_info is mi


# ================ END response tests ===============
