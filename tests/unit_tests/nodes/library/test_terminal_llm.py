import pytest
import requestcompletion as rc
from requestcompletion.llm import MessageHistory, SystemMessage, UserMessage
from requestcompletion.nodes.library import TerminalLLM, terminal_llm
from requestcompletion.exceptions import NodeCreationError, NodeInvocationError


# ================================================ START terminal_llm basic functionality =========================================================
@pytest.mark.asyncio
async def test_terminal_llm_instantiate_and_invoke(mock_llm, mock_chat_function):
    class MockLLM(TerminalLLM):
        @classmethod
        def pretty_name(cls):
            return "Mock LLM"
        
    mh = MessageHistory([SystemMessage("system prompt"), UserMessage("hello")])
    node = MockLLM(message_history=mh, model=mock_llm(chat=mock_chat_function))
    # with rc.Runner() as runner:
    result = await node.invoke()
    assert result == "dummy content"

@pytest.mark.asyncio
async def test_terminal_llm_easy_usage_wrapper_invoke(mock_llm, mock_chat_function):
    node = terminal_llm(
        pretty_name="Mock LLM",
        system_message="system prompt",
        model=mock_llm(chat=mock_chat_function),
    )
    mh = MessageHistory([UserMessage("hello")])
    result = await rc.call(node, message_history=mh)
    assert result == "dummy content"

def test_terminal_llm_easy_usage_wrapper_classmethods(mock_llm):
    NodeClass = terminal_llm(
        pretty_name="Mock LLM",
        system_message="system prompt",
        model=mock_llm(),
    )
    assert NodeClass.pretty_name() == "Mock LLM"

@pytest.mark.asyncio
async def test_terminal_llm_system_message_string_inserts_system_message(mock_llm):
    NodeClass = terminal_llm(
        pretty_name="TestTerminalNode",
        system_message="system prompt",
        model=mock_llm(),
    )
    mh = MessageHistory([UserMessage("hello")])
    node = NodeClass(message_history=mh)
    # The first message should be a system message
    assert node.message_hist[0].role == "system"
    assert node.message_hist[0].content == "system prompt"
# ================================================ END terminal_llm basic functionality ===========================================================

# ================================================ START terminal_llm Exception testing =========================================================== 
# =================== START Easy Usage Node Creation ===================
@pytest.mark.asyncio
async def test_terminal_llm_missing_tool_details_easy_usage(mock_llm, encoder_system_message):
    # Test case where tool_params is given but tool_details is not
    encoder_tool_params = {
        rc.llm.Parameter("text_input", "string", "The string to encode.")
    }

    with pytest.raises(
        NodeCreationError, match="Tool parameters are provided, but tool details are missing."
    ):
        encoder_wo_tool_details = rc.library.terminal_llm(
            pretty_name="Encoder",
            system_message=encoder_system_message,
            model=mock_llm(),
            tool_params=encoder_tool_params,  # Intentionally omitting tool_details
        )
        


@pytest.mark.asyncio
async def test_terminal_llm_no_pretty_name_with_tool_easy_usage(mock_llm, encoder_system_message):
    # Test case where tool is configured but pretty_name is missing
    
    with pytest.raises(
        NodeCreationError, match="You must provide a pretty_name when using this node as a tool"
    ):
        encoder_tool_details = "A tool used to encode text into bytes."

        encoder_tool_params = {
            rc.llm.Parameter("text_input", "string", "The string to encode.")
        }
        encoder_wo_pretty_name = rc.library.terminal_llm(
                # Intentionally omitting pretty_name
                system_message=encoder_system_message,
                model=mock_llm(),
                tool_details=encoder_tool_details,
                tool_params=encoder_tool_params,
            )

@pytest.mark.asyncio
async def test_terminal_llm_tool_duplicate_parameter_names_easy_usage(
    mock_llm, encoder_system_message
):
    # Test with duplicate parameter names
    encoder_tool_details = "A tool with duplicate parameter names."
    encoder_tool_params = {
        rc.llm.Parameter("text_input", "string", "The string to encode."),
        rc.llm.Parameter("text_input", "string", "Duplicate parameter name."),
    }

    with pytest.raises(
        NodeCreationError, match="Duplicate parameter names are not allowed."
    ):
       encoder_w_duplicate_param = rc.library.terminal_llm(
            pretty_name="Encoder",
            system_message=encoder_system_message,
            model=mock_llm(),
            tool_details=encoder_tool_details,
            tool_params=encoder_tool_params,
        )
# =================== END Easy Usage Node Creation ===================
# =================== START Class Based Node Creation ===================

@pytest.mark.asyncio
async def test_no_pretty_name_class_based(mock_llm, encoder_system_message):
    class Encoder_wo_pretty_name(rc.library.TerminalLLM): 
        def __init__(
                self,
                message_history: rc.llm.MessageHistory,
                model: rc.llm.ModelBase = mock_llm(),
            ):
                message_history = [x for x in message_history if x.role != "system"]
                message_history.insert(0, encoder_system_message)
                super().__init__(
                    message_history=message_history,
                    model=model,
                )

    with pytest.raises(
        TypeError, match="Can't instantiate abstract class Encoder_wo_pretty_name"
    ):
        _ = await rc.call(Encoder_wo_pretty_name, message_history=rc.llm.MessageHistory([rc.llm.UserMessage("encoder 'hello world!'")]))
        

@pytest.mark.asyncio
async def test_tool_info_not_classmethod(mock_llm, encoder_system_message):
    with pytest.raises(
        NodeCreationError, match="The 'tool_info' method must be a @classmethod."
    ):
        class Encoder(rc.library.TerminalLLM): 
            def __init__(
                    self,
                    message_history: rc.llm.MessageHistory,
                    model: rc.llm.ModelBase = mock_llm(),
                ):
                    message_history = [x for x in message_history if x.role != "system"]
                    message_history.insert(0, encoder_system_message)
                    super().__init__(
                        message_history=message_history,
                        model=model,
                    )
            
            @classmethod
            def pretty_name(self) -> str:
                return "Encoder Node"
            
            def tool_info(self) -> rc.llm.Tool:
                return rc.llm.Tool(
                    name="Encoder",
                    detail="A tool used to encode text into bytes.",
                    parameters={
                        rc.llm.Parameter(
                            name="text_input",
                            param_type="string",
                            description="The string to encode.",
                        )
                    },
                )
        
# =================== END Class Based Node Creation ===================
# =================== START invocation exceptions =====================
@pytest.mark.asyncio
async def test_no_message_history_easy_usage(mock_llm):
    simple_agent = rc.library.terminal_llm(
            pretty_name="Encoder",
            model=mock_llm(),
        )
    
    with pytest.raises(NodeInvocationError, match="Message history must contain at least one message"):
        await rc.call(simple_agent, message_history=rc.llm.MessageHistory([]))

@pytest.mark.asyncio
async def test_no_message_history_class_based():
    class Encoder(rc.library.TerminalLLM):
        def __init__(self, message_history: rc.llm.MessageHistory, model: rc.llm.ModelBase = None):
            super().__init__(message_history=message_history, model=model)

        @classmethod 
        def pretty_name(cls) -> str:
            return "Encoder"

    with pytest.raises(NodeInvocationError, match="Message history must contain at least one message"):
        _ = await rc.call(Encoder, message_history=rc.llm.MessageHistory([]))
    
@pytest.mark.asyncio
async def test_system_message_as_a_string_class_based(mock_llm):
    # if a string is provided as system_message in a class based initialization, we are throwing an error
    class Encoder(rc.library.TerminalLLM): 
        def __init__(
                self,
                message_history: rc.llm.MessageHistory,
                model: rc.llm.ModelBase = mock_llm(),
            ):
                message_history = [x for x in message_history if x.role != "system"]
                message_history.insert(0, "You are a helpful assistant that can encode text into bytes.")
                super().__init__(
                    message_history=message_history,
                    model=model,
                )
        @classmethod
        def pretty_name(cls) -> str:
            return "Simple Node"

    with pytest.raises(NodeInvocationError, match="Message history must be a list of Message objects"):
        response = await rc.call(Encoder, message_history=rc.llm.MessageHistory([rc.llm.UserMessage("hello world")]))
# =================== END invocation exceptions =====================
# ================================================ END terminal_llm Exception testing ===========================================================
