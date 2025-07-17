import pytest
import requestcompletion as rc
from pydantic import BaseModel, Field
from requestcompletion.nodes.library import tool_call_llm, StructuredToolCallLLM, structured_tool_call_llm
from requestcompletion.exceptions import NodeCreationError
from requestcompletion.llm import MessageHistory, SystemMessage, UserMessage
# =========================== Basic functionality ==========================

def test_structured_tool_call_llm_init(mock_llm, schema, mock_tool):
    class MockStructuredToolCallLLM(StructuredToolCallLLM):
        @classmethod
        def schema(cls):
            return schema
        
        @classmethod
        def pretty_name(cls):
            return "Mock Structured ToolCallLLM"
        
        def connected_nodes(self):
            return {mock_tool}
    
    mh = MessageHistory([SystemMessage("system prompt"), UserMessage("extract value")])
    node = MockStructuredToolCallLLM(
        message_history=mh,
        llm_model=mock_llm(),
    )
    assert hasattr(node, "structured_resp_node")

def test_structured_tool_call_llm_return_output_success(mock_tool, mock_llm, schema):
    class MockStructuredToolCallLLM(StructuredToolCallLLM):
        @classmethod
        def schema(cls):
            return schema
        
        @classmethod
        def pretty_name(cls):
            return "Mock Structured ToolCallLLM"
        
        def connected_nodes(self):
            return {mock_tool}
    
    mh = MessageHistory([SystemMessage("system prompt"), UserMessage("extract value")])
    node = MockStructuredToolCallLLM(
        message_history=mh,
        llm_model=mock_llm(),
    )
    node.structured_output = schema(value=123)
    assert node.return_output().value == 123

def test_structured_tool_call_llm_return_output_exception(mock_llm, schema, mock_tool):
    node = structured_tool_call_llm(
        system_message="system prompt",
        connected_nodes={mock_tool},
        llm_model=mock_llm(),
        schema=schema,
        tool_details="Extracts a value.",
        tool_params=None,
        pretty_name="Mock Structured ToolCallLLM",
    )
    mh = MessageHistory([SystemMessage("system prompt"), UserMessage("extract value")])
    node = node(mh, mock_llm())
    node.structured_output = ValueError("fail")
    with pytest.raises(ValueError):
        node.return_output()

def test_structured_llm_easy_usage_wrapper(mock_llm, schema, mock_tool):
    mh = MessageHistory([SystemMessage("system prompt"), UserMessage("extract value")])
    node = structured_tool_call_llm(
        system_message="system prompt",
        connected_nodes={mock_tool},
        llm_model=mock_llm(),
        schema=schema,
        tool_details="Extracts a value.",
        tool_params=None,
        pretty_name="Mock Structured ToolCallLLM",
    )
    node = node(mh, mock_llm())
    assert hasattr(node, "structured_resp_node")


# =========================== Exception testing ============================
# Not using the ones in conftest.py because we will have to use lazy_fixtures for that. lazy_fixture is not very well supported in pytest (better to avaoid it)
class SimpleOutput(BaseModel):
    text: str = Field(description="The text to return")


@pytest.mark.parametrize(
    "llm_function, connected_nodes",
    [
        (rc.library.structured_tool_call_llm, {rc.library.from_function(lambda: "test")}),
        (rc.library.structured_llm, None),
    ],
    ids=["tool_call_llm", "structured_llm"],
)
@pytest.mark.parametrize(
    "schema, tool_details, tool_params, expected_exception, match",
    [
        # Test: tool_params provided but tool_details is missing
        (
            SimpleOutput,
            None,
            [
                rc.llm.Parameter(
                    name="param1", param_type="string", description="A test parameter."
                )
            ],
            NodeCreationError,
            "Tool parameters are provided, but tool details are missing.",
        ),
        # Test: Duplicate parameter names in tool_params
        (
            SimpleOutput,
            "A test tool",
            [
                rc.llm.Parameter(
                    name="param1", param_type="string", description="A test parameter."
                ),
                rc.llm.Parameter(
                    name="param1",
                    param_type="string",
                    description="A duplicate parameter.",
                ),
            ],
            NodeCreationError,
            "Duplicate parameter names are not allowed.",
        ),
    ],
)
def test_structured_llm_tool_errors(
    schema,
    tool_details,
    tool_params,
    llm_function,
    connected_nodes,
    expected_exception,
    match,
):
    kwargs = {
        "schema": schema,
        "tool_details": tool_details,
        "tool_params": tool_params,
    }
    if connected_nodes is not None:
        kwargs["connected_nodes"] = connected_nodes

    with pytest.raises(expected_exception, match=match):
        llm_function(**kwargs)
