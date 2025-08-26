import pytest
from railtracks.llm.content import ToolCall, ToolResponse, Stream

@pytest.fixture
def valid_tool_call():
    return ToolCall(identifier="123", name="example_tool", arguments={"arg1": "value1"})


@pytest.fixture
def valid_tool_response():
    return ToolResponse(identifier="123", name="example_tool", result="success")

# ---- Stream fixtures ----

@pytest.fixture
def simple_string_generator():
    def _gen():
        yield "chunk 1"
        yield "chunk 2"
    return _gen()

@pytest.fixture
def empty_string_generator():
    def _gen():
        if False:
            yield
    return _gen()

# ---- Stream instance fixtures ----

@pytest.fixture
def stream_with_final_message(simple_string_generator):
    return Stream(streamer=simple_string_generator, final_message="Final!")

@pytest.fixture
def stream_without_final_message(simple_string_generator):
    return Stream(streamer=simple_string_generator)



class TestToolCall:
    def test_tool_call_str(self):
        tool_call = ToolCall(identifier="123", name="example_tool", arguments={"arg1": "value1", "arg2": "value2"})
        assert str(tool_call) == "example_tool({'arg1': 'value1', 'arg2': 'value2'})"


    def test_tool_response_str(self):
        tool_response = ToolResponse(identifier="123", name="example_tool", result="success")
        assert str(tool_response) == "example_tool -> success"


    @pytest.mark.parametrize(
        "invalid_identifier, invalid_name, invalid_arguments, expected_exception",
        [
            (None, "example_tool", {"arg1": "value1"}, ValueError),
            ("123", None, {"arg1": "value1"}, ValueError),
            ("123", "example_tool", None, ValueError),
        ],
    )
    def test_invalid_tool_call(self, invalid_identifier, invalid_name, invalid_arguments, expected_exception):
        with pytest.raises(expected_exception):
            ToolCall(identifier=invalid_identifier, name=invalid_name, arguments=invalid_arguments)


class TestToolResponse:
    @pytest.mark.parametrize(
        "invalid_identifier, invalid_name, invalid_result, expected_exception",
        [
            (None, "example_tool", "success", ValueError),
            ("123", None, "success", ValueError),
            ("123", "example_tool", None, ValueError),
        ],
    )
    def test_invalid_tool_response(self, invalid_identifier, invalid_name, invalid_result, expected_exception):
        with pytest.raises(expected_exception):
            ToolResponse(identifier=invalid_identifier, name=invalid_name, result=invalid_result)


    def test_tool_call_fixture(self, valid_tool_call):
        assert valid_tool_call.identifier == "123"
        assert valid_tool_call.name == "example_tool"
        assert valid_tool_call.arguments == {"arg1": "value1"}


    def test_tool_response_fixture(self, valid_tool_response):
        assert valid_tool_response.identifier == "123"
        assert valid_tool_response.name == "example_tool"
        assert valid_tool_response.result == "success"

class TestStream:
    def test_stream_construction_with_valid_generator(self, simple_string_generator):
        s = Stream(streamer=simple_string_generator)
        assert s.streamer is simple_string_generator

    def test_stream_construction_with_final_message(self, simple_string_generator):
        s = Stream(streamer=simple_string_generator, final_message="Done")
        assert s.final_message == "Done"

    def test_stream_construction_with_no_final_message(self, simple_string_generator):
        s = Stream(streamer=simple_string_generator)
        assert s.final_message == ""

    def test_stream_properties(self, stream_with_final_message, simple_string_generator):
        assert stream_with_final_message.streamer is simple_string_generator
        assert stream_with_final_message.final_message == "Final!"

    def test_stream_property_streamer_type(self, stream_with_final_message):
        # The streamer must be a generator
        assert hasattr(stream_with_final_message.streamer, "__iter__")

    def test_stream_with_empty_generator(self, empty_string_generator):
        s = Stream(streamer=empty_string_generator)
        # Final message is empty by default
        assert s.final_message == ""
        # The streamer is empty
        assert list(s.streamer) == []

    def test_stream_raises_type_error_on_non_generator(self):
        not_a_generator = "I am not a generator"
        with pytest.raises(TypeError):
            Stream(streamer=not_a_generator)

    def test_stream_repr_and_str(self, stream_without_final_message):
        # __str__ and __repr__ should be identical
        s = stream_without_final_message
        assert str(s) == repr(s)
        assert "Stream(streamer=" in str(s)

    def test_stream_repr_content(self, stream_with_final_message):
        s = stream_with_final_message
        # The repr output should contain the class name and show it's a generator object
        repr_str = repr(s)
        assert "Stream(streamer=" in repr_str
        assert "generator object" in repr_str
        assert "at 0x" in repr_str  # generator's memory address representation