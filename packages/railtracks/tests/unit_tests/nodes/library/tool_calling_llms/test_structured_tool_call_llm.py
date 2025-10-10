import pytest
import railtracks as rt
from pydantic import BaseModel, Field

from railtracks.llm.response import Response
from railtracks.built_nodes.easy_usage_wrappers.helpers import structured_tool_call_llm, structured_llm
from railtracks.exceptions import NodeCreationError, LLMError
from railtracks.llm import MessageHistory, SystemMessage, UserMessage, AssistantMessage

from railtracks.built_nodes.concrete import StructuredToolCallLLM


# =========================== Basic functionality ==========================

def test_structured_tool_call_llm_init(mock_llm, schema, mock_tool):
    class MockStructuredToolCallLLM(StructuredToolCallLLM[schema]):
        @classmethod
        def output_schema(cls):
            return schema
        
        @classmethod
        def name(cls):
            return "Mock Structured ToolCallLLM"
        
        def tool_nodes(self):
            return {mock_tool}
    
    mh = MessageHistory([SystemMessage("system prompt"), UserMessage("extract value")])
    node = MockStructuredToolCallLLM(
        user_input=mh,
        llm=mock_llm(),
    )
    assert hasattr(node, "structured_resp_node")

def test_structured_tool_call_llm_return_output_success(mock_tool, mock_llm, schema):
    class MockStructuredToolCallLLM(StructuredToolCallLLM):
        @classmethod
        def output_schema(cls):
            return schema
        
        @classmethod
        def name(cls):
            return "Mock Structured ToolCallLLM"
        
        @classmethod
        def tool_nodes(cls):
            return {mock_tool}
    
    mh = MessageHistory([SystemMessage("system prompt"), UserMessage("extract value")])
    node = MockStructuredToolCallLLM(
        user_input=mh,
        llm=mock_llm(),
    )

    last_message = AssistantMessage(schema(value=123))
    node.message_hist.append(last_message)
    assert node.return_output(last_message).structured.value == 123

def test_structured_message_hist_tool_call_llm_return_output_success(mock_tool, mock_llm, schema):
    class MockStructuredMessHistToolCallLLM(StructuredToolCallLLM):
    
        @classmethod
        def output_schema(cls):
            return schema
        
        @classmethod
        def name(cls):
            return "Mock Structured ToolCallLLM"
        
        @classmethod
        def tool_nodes(cls):
            return {mock_tool}
    
    mh = MessageHistory([SystemMessage("system prompt"), UserMessage("extract value")])
    node = MockStructuredMessHistToolCallLLM(
        user_input=mh,
        llm=mock_llm(),
    )
    last_message = AssistantMessage(schema(value=123))
    node.message_hist.append(last_message)
    assert node.return_output(last_message).content.value == 123
    assert any(x.role is not SystemMessage for x in node.return_output(last_message).message_history)

@pytest.mark.asyncio
async def test_structured_tool_call_llm_return_output_exception(mock_llm, schema, mock_tool):
    def mock_structured(message_history, base_model):
        raise ValueError("fail")
    
    model = mock_llm(AssistantMessage("Hello world"))
    model._structured = mock_structured

    node = structured_tool_call_llm(
        system_message="system prompt",
        tool_nodes={mock_tool},
        llm=model,
        output_schema=schema,
        tool_details="Extracts a value.",
        tool_params=None,
        name="Mock Structured ToolCallLLM",
    )
    mh = MessageHistory([SystemMessage("system prompt"), UserMessage("extract value")])

    node = node(mh)

    with pytest.raises(LLMError):
        await node.invoke()


def test_structured_llm_easy_usage_wrapper(mock_llm, schema, mock_tool):
    mh = MessageHistory([SystemMessage("system prompt"), UserMessage("extract value")])
    node = structured_tool_call_llm(
        system_message="system prompt",
        tool_nodes={mock_tool},
        llm=mock_llm(),
        output_schema=schema,
        tool_details="Extracts a value.",
        tool_params=None,
        name="Mock Structured ToolCallLLM",
    )
    node = node(mh, mock_llm())
    assert hasattr(node, "structured_resp_node")

def test_structured_tool_call_llm_instantiate_with_string(mock_llm, schema, mock_tool):
    """Test that StructuredToolCallLLM can be instantiated with a string input."""
    class MockStructuredToolCallLLM(StructuredToolCallLLM):
        @classmethod
        def output_schema(cls):
            return schema
        
        @classmethod
        def name(cls):
            return "Mock Structured ToolCallLLM"
        
        @classmethod
        def system_message(cls):
            return "system prompt"
        
        @classmethod
        def tool_nodes(cls):
            return {mock_tool}
        
    node = MockStructuredToolCallLLM(user_input="extract value", llm=mock_llm())
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
        def output_schema(cls):
            return schema
        
        @classmethod
        def name(cls):
            return "Mock Structured ToolCallLLM"
        
        @classmethod
        def system_message(cls):
            return "system prompt"
        
        @classmethod
        def tool_nodes(cls):
            return {mock_tool}
        
    user_msg = UserMessage("extract value")
    node = MockStructuredToolCallLLM(user_input=user_msg, llm=mock_llm())
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
        tool_nodes={mock_tool},
        llm=mock_llm(),
        output_schema=schema,
        tool_details="Extracts a value.",
        tool_params=None,
        name="Mock Structured ToolCallLLM",
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
        tool_nodes={mock_tool},
        llm=mock_llm(),
        output_schema=schema,
        tool_details="Extracts a value.",
        tool_params=None,
        name="Mock Structured ToolCallLLM",
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
    "llm_function, tool_nodes",
    [
        (structured_tool_call_llm, {rt.function_node(lambda: "test")}),
        (structured_llm, None),
    ],
    ids=["tool_call_llm", "structured_llm"],
)
@pytest.mark.parametrize(
    "output_schema, tool_details, tool_params, expected_exception, match",
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
    output_schema,
    tool_details,
    tool_params,
    llm_function,
    tool_nodes,
    expected_exception,
    match,
):
    kwargs = {
        "output_schema": output_schema,
        "tool_details": tool_details,
        "tool_params": tool_params,
    }
    if tool_nodes is not None:
        kwargs["tool_nodes"] = tool_nodes

    with pytest.raises(expected_exception, match=match):
        llm_function(**kwargs)
