import pytest
import requestcompletion as rc
from pydantic import BaseModel, Field
from requestcompletion.nodes.library import tool_call_llm, StructuredToolCallLLM, structured_tool_call_llm
from requestcompletion.exceptions import NodeCreationError
from requestcompletion.llm import MessageHistory, SystemMessage, UserMessage
# =========================== Basic functionality ==========================

def test_structured_tool_call_llm_init(mock_llm, output_model, mock_tool):
    class MockStructuredToolCallLLM(StructuredToolCallLLM):
        @classmethod
        def output_model(cls):
            return output_model
        
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

def test_structured_tool_call_llm_return_output_success(mock_tool, mock_llm, output_model):
    class MockStructuredToolCallLLM(StructuredToolCallLLM):
        @classmethod
        def output_model(cls):
            return output_model
        
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
    node.structured_output = output_model(value=123)
    assert node.return_output().value == 123

def test_structured_tool_call_llm_return_output_exception(mock_llm, output_model, mock_tool):
    node = structured_tool_call_llm(
        system_message="system prompt",
        connected_nodes={mock_tool},
        llm_model=mock_llm(),
        output_model=output_model,
        tool_details="Extracts a value.",
        tool_params=None,
        pretty_name="Mock Structured ToolCallLLM",
    )
    mh = MessageHistory([SystemMessage("system prompt"), UserMessage("extract value")])
    node = node(mh, mock_llm())
    node.structured_output = ValueError("fail")
    with pytest.raises(ValueError):
        node.return_output()

def test_structured_llm_easy_usage_wrapper(mock_llm, output_model, mock_tool):
    mh = MessageHistory([SystemMessage("system prompt"), UserMessage("extract value")])
    node = structured_tool_call_llm(
        system_message="system prompt",
        connected_nodes={mock_tool},
        llm_model=mock_llm(),
        output_model=output_model,
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
    "output_model, tool_details, tool_params, expected_exception, match",
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
    output_model,
    tool_details,
    tool_params,
    llm_function,
    connected_nodes,
    expected_exception,
    match,
):
    kwargs = {
        "output_model": output_model,
        "tool_details": tool_details,
        "tool_params": tool_params,
    }
    if connected_nodes is not None:
        kwargs["connected_nodes"] = connected_nodes

    with pytest.raises(expected_exception, match=match):
        llm_function(**kwargs)


@pytest.mark.asyncio  # can remove this test once we have support for output_model with output_type = MessageHistory. See Line 30 in src/requestcompletion/nodes/library/easy_usage_wrappers/tool_call_llm.py
async def test_structured_tool_call_with_output_model_and_output_type(
    mock_llm, math_output_model
):
    """Tool call llm init with output model and output_type = message_history should raise an error."""
    rng_node = rc.library.terminal_llm(
        pretty_name="RNG Tool",
        system_message="You are a helful assistant that can generate 5 random numbers between 1 and 100.",
        llm_model=mock_llm(),
        tool_details="A tool used to generate 5 random integers between 1 and 100.",
        tool_params=None,
    )

    with pytest.raises(
        NotImplementedError,
        match="MessageHistory output type is not supported with output_model at the moment.",
    ):
        _ = rc.library.structured_tool_call_llm(
            connected_nodes={rng_node},
            pretty_name="Math Node",
            system_message="You are a math genius that calls the RNG tool to generate 5 random numbers between 1 and 100 and gives the sum of those numbers.",
            llm_model=mock_llm(),
            output_type="MessageHistory",
            output_model=math_output_model,
        )
