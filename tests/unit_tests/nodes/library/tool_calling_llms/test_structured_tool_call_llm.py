import pytest
import railtracks as rt
from pydantic import BaseModel, Field

from railtracks.llm.response import Response
from railtracks.nodes.library import structured_tool_call_llm
from railtracks.exceptions import NodeCreationError, LLMError
from railtracks.llm import MessageHistory, SystemMessage, UserMessage, AssistantMessage

from railtracks.nodes.library.tool_calling_llms.structured_tool_call_llm_base import StructuredToolCallLLM


# =========================== Basic functionality ==========================

def test_structured_tool_call_llm_init(mock_llm, schema, mock_tool):
    class MockStructuredToolCallLLM(StructuredToolCallLLM[schema]):
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
        user_input=mh,
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
        user_input=mh,
        llm_model=mock_llm(),
    )
    node.message_hist.append(AssistantMessage(schema(value=123)))
    assert node.return_output().structured.value == 123

def test_structured_message_hist_tool_call_llm_return_output_success(mock_tool, mock_llm, schema):
    class MockStructuredMessHistToolCallLLM(StructuredToolCallLLM):
    
        @classmethod
        def schema(cls):
            return schema
        
        @classmethod
        def pretty_name(cls):
            return "Mock Structured ToolCallLLM"
        
        @classmethod
        def connected_nodes(cls):
            return {mock_tool}
    
    mh = MessageHistory([SystemMessage("system prompt"), UserMessage("extract value")])
    node = MockStructuredMessHistToolCallLLM(
        user_input=mh,
        llm_model=mock_llm(),
    )
    node.message_hist.append(AssistantMessage(schema(value=123)))
    assert node.return_output().content.value == 123
    assert any(x.role is not SystemMessage for x in node.return_output().message_history)

@pytest.mark.asyncio
async def test_structured_tool_call_llm_return_output_exception(mock_llm, schema, mock_tool):
    def mock_structured(message_history, base_model):
        raise ValueError("fail")

    node = structured_tool_call_llm(
        system_message="system prompt",
        connected_nodes={mock_tool},
        llm_model=mock_llm(structured=mock_structured,
             chat_with_tools=lambda x, tools: Response(message=AssistantMessage("Hello world"))),
        schema=schema,
        tool_details="Extracts a value.",
        tool_params=None,
        pretty_name="Mock Structured ToolCallLLM",
    )
    mh = MessageHistory([SystemMessage("system prompt"), UserMessage("extract value")])

    node = node(mh)

    with pytest.raises(LLMError):
        await node.invoke()


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

def test_structured_tool_call_llm_instantiate_with_string(mock_llm, schema, mock_tool):
    """Test that StructuredToolCallLLM can be instantiated with a string input."""
    class MockStructuredToolCallLLM(StructuredToolCallLLM):
        @classmethod
        def schema(cls):
            return schema
        
        @classmethod
        def pretty_name(cls):
            return "Mock Structured ToolCallLLM"
        
        @classmethod
        def system_message(cls):
            return "system prompt"
        
        @classmethod
        def connected_nodes(cls):
            return {mock_tool}
        
    node = MockStructuredToolCallLLM(user_input="extract value", llm_model=mock_llm())
    # Verify that the string was converted to a MessageHistory with a UserMessage
    assert len(node.message_hist) == 2  # System message + UserMessage
    assert node.message_hist[0].role == "system"
    assert node.message_hist[0].content == "system prompt"
    assert node.message_hist[1].role == "user"
    assert node.message_hist[1].content == "extract value"

def test_structured_tool_call_llm_instantiate_with_user_message(mock_llm, schema, mock_tool):
    """Test that StructuredToolCallLLM can be instantiated with a UserMessage input."""
    class MockStructuredToolCallLLM(StructuredToolCallLLM):
        @classmethod
        def schema(cls):
            return schema
        
        @classmethod
        def pretty_name(cls):
            return "Mock Structured ToolCallLLM"
        
        @classmethod
        def system_message(cls):
            return "system prompt"
        
        @classmethod
        def connected_nodes(cls):
            return {mock_tool}
        
    user_msg = UserMessage("extract value")
    node = MockStructuredToolCallLLM(user_input=user_msg, llm_model=mock_llm())
    # Verify that the UserMessage was converted to a MessageHistory
    assert len(node.message_hist) == 2  # System message + UserMessage
    assert node.message_hist[0].role == "system"
    assert node.message_hist[0].content == "system prompt"
    assert node.message_hist[1].role == "user"
    assert node.message_hist[1].content == "extract value"

def test_structured_tool_call_llm_easy_usage_with_string(mock_llm, schema, mock_tool):
    """Test that the easy usage wrapper can be instantiated with a string input."""
    node_class = structured_tool_call_llm(
        system_message="system prompt",
        connected_nodes={mock_tool},
        llm_model=mock_llm(),
        schema=schema,
        tool_details="Extracts a value.",
        tool_params=None,
        pretty_name="Mock Structured ToolCallLLM",
    )
    
    node = node_class(user_input="extract value")
    # Verify that the string was converted to a MessageHistory with a UserMessage
    assert len(node.message_hist) == 2  # System message + UserMessage
    assert node.message_hist[0].role == "system"
    assert node.message_hist[0].content == "system prompt"
    assert node.message_hist[1].role == "user"
    assert node.message_hist[1].content == "extract value"

def test_structured_tool_call_llm_easy_usage_with_user_message(mock_llm, schema, mock_tool):
    """Test that the easy usage wrapper can be instantiated with a UserMessage input."""
    node_class = structured_tool_call_llm(
        system_message="system prompt",
        connected_nodes={mock_tool},
        llm_model=mock_llm(),
        schema=schema,
        tool_details="Extracts a value.",
        tool_params=None,
        pretty_name="Mock Structured ToolCallLLM",
    )
    
    user_msg = UserMessage("extract value")
    node = node_class(user_input=user_msg)
    # Verify that the UserMessage was converted to a MessageHistory
    assert len(node.message_hist) == 2  # System message + UserMessage
    assert node.message_hist[0].role == "system"
    assert node.message_hist[0].content == "system prompt"
    assert node.message_hist[1].role == "user"
    assert node.message_hist[1].content == "extract value"


# =========================== Exception testing ============================
# Not using the ones in conftest.py because we will have to use lazy_fixtures for that. lazy_fixture is not very well supported in pytest (better to avaoid it)
class SimpleOutput(BaseModel):
    text: str = Field(description="The text to return")


@pytest.mark.parametrize(
    "llm_function, connected_nodes",
    [
        (rt.library.structured_tool_call_llm, {rt.library.from_function(lambda: "test")}),
        (rt.library.structured_llm, None),
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
                rt.llm.Parameter(
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
                rt.llm.Parameter(
                    name="param1", param_type="string", description="A test parameter."
                ),
                rt.llm.Parameter(
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
