import pytest
import railtracks as rt
from railtracks.llm import MessageHistory, SystemMessage, UserMessage
from railtracks.nodes.library import TerminalLLM, terminal_llm
from railtracks.exceptions import NodeCreationError, NodeInvocationError


# ================================================ START terminal_llm basic functionality =========================================================
@pytest.mark.asyncio
async def test_terminal_llm_instantiate_and_invoke(mock_llm, mock_chat_function):
    class MockLLM(TerminalLLM):
        @classmethod
        def pretty_name(cls):
            return "Mock LLM"
        
    mh = MessageHistory([SystemMessage("system prompt"), UserMessage("hello")])
    node = MockLLM(user_input=mh, llm_model=mock_llm(chat=mock_chat_function))
    # with rt.Runner() as runner:
    result = await node.invoke()
    assert result.text == "dummy content"

@pytest.mark.asyncio
async def test_terminal_llm_instantiate_with_string(mock_llm, mock_chat_function):
    """Test that TerminalLLM can be instantiated with a string input."""
    class MockLLM(TerminalLLM):
        @classmethod
        def pretty_name(cls):
            return "Mock LLM"

        @classmethod
        def system_message(cls):
            return "system prompt"

    node = MockLLM(user_input="hello", llm_model=mock_llm(chat=mock_chat_function))
    # Verify that the string was converted to a MessageHistory with a UserMessage
    assert len(node.message_hist) == 2  # System message + UserMessage
    assert node.message_hist[0].role == "system"
    assert node.message_hist[0].content == "system prompt"
    assert node.message_hist[1].role == "user"
    assert node.message_hist[1].content == "hello"

    result = await node.invoke()
    assert result.text == "dummy content"

@pytest.mark.asyncio
async def test_terminal_llm_instantiate_with_user_message(mock_llm, mock_chat_function):
    """Test that TerminalLLM can be instantiated with a UserMessage input."""
    class MockLLM(TerminalLLM):
        @classmethod
        def pretty_name(cls):
            return "Mock LLM"

        @classmethod
        def system_message(cls):
            return "system prompt"

    user_msg = UserMessage("hello")
    node = MockLLM(user_input=user_msg, llm_model=mock_llm(chat=mock_chat_function))
    # Verify that the UserMessage was converted to a MessageHistory
    assert len(node.message_hist) == 2  # System message + UserMessage
    assert node.message_hist[0].role == "system"
    assert node.message_hist[0].content == "system prompt"
    assert node.message_hist[1].role == "user"
    assert node.message_hist[1].content == "hello"

    result = await node.invoke()
    assert result.text == "dummy content"

@pytest.mark.asyncio
async def test_terminal_llm_easy_usage_wrapper_invoke(mock_llm, mock_chat_function):
    node = terminal_llm(
        pretty_name="Mock LLM",
        system_message="system prompt",
        llm_model=mock_llm(chat=mock_chat_function),
    )
    mh = MessageHistory([UserMessage("hello")])
    result = await rt.call(node, user_input=mh)
    assert result.text == "dummy content"

def test_terminal_llm_easy_usage_wrapper_classmethods(mock_llm):
    NodeClass = terminal_llm(
        pretty_name="Mock LLM",
        system_message="system prompt",
        llm_model=mock_llm(),
    )
    assert NodeClass.pretty_name() == "Mock LLM"

@pytest.mark.asyncio
async def test_terminal_llm_system_message_string_inserts_system_message(mock_llm):
    NodeClass = terminal_llm(
        pretty_name="TestTerminalNode",
        system_message="system prompt",
        llm_model=mock_llm(),
    )
    mh = MessageHistory([UserMessage("hello")])
    node = NodeClass(user_input=mh)
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
        rt.llm.Parameter("text_input", "string", "The string to encode.")
    }

    with pytest.raises(
        NodeCreationError, match="Tool parameters are provided, but tool details are missing."
    ):
        encoder_wo_tool_details = rt.library.terminal_llm(
            pretty_name="Encoder",
            system_message=encoder_system_message,
            llm_model=mock_llm(),
            tool_params=encoder_tool_params,  # Intentionally omitting tool_details
        )
        

@pytest.mark.asyncio
async def test_terminal_llm_tool_duplicate_parameter_names_easy_usage(
    mock_llm, encoder_system_message
):
    # Test with duplicate parameter names
    encoder_tool_details = "A tool with duplicate parameter names."
    encoder_tool_params = {
        rt.llm.Parameter("text_input", "string", "The string to encode."),
        rt.llm.Parameter("text_input", "string", "Duplicate parameter name."),
    }

    with pytest.raises(
        NodeCreationError, match="Duplicate parameter names are not allowed."
    ):
       encoder_w_duplicate_param = rt.library.terminal_llm(
            pretty_name="Encoder",
            system_message=encoder_system_message,
            llm_model=mock_llm(),
            tool_details=encoder_tool_details,
            tool_params=encoder_tool_params,
        )
# =================== END Easy Usage Node Creation ===================
# =================== START Class Based Node Creation ===================


@pytest.mark.asyncio
async def test_tool_info_not_classmethod(mock_llm, encoder_system_message):
    with pytest.raises(
        NodeCreationError, match="The 'tool_info' method must be a @classmethod."
    ):
        class Encoder(rt.library.TerminalLLM):
            def __init__(
                    self,
                    user_input: rt.llm.MessageHistory,
                    llm_model: rt.llm.ModelBase = mock_llm(),
                ):
                    user_input = [x for x in user_input if x.role != "system"]
                    user_input.insert(0, encoder_system_message)
                    super().__init__(
                        user_input=user_input,
                        llm_model=llm_model,
                    )
            
            @classmethod
            def pretty_name(self) -> str:
                return "Encoder Node"
            
            def tool_info(self) -> rt.llm.Tool:
                return rt.llm.Tool(
                    name="Encoder",
                    detail="A tool used to encode text into bytes.",
                    parameters={
                        rt.llm.Parameter(
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
    simple_agent = rt.library.terminal_llm(
            pretty_name="Encoder",
            llm_model=mock_llm(),
        )
    
    with pytest.raises(NodeInvocationError, match="Message history must contain at least one message"):
        await rt.call(simple_agent, user_input=rt.llm.MessageHistory([]))

@pytest.mark.asyncio
async def test_no_message_history_class_based():
    class Encoder(rt.library.TerminalLLM):
        def __init__(self, user_input: rt.llm.MessageHistory, llm_model: rt.llm.ModelBase = None):
            super().__init__(user_input=user_input, llm_model=llm_model)

        @classmethod 
        def pretty_name(cls) -> str:
            return "Encoder"

    with pytest.raises(NodeInvocationError, match="Message history must contain at least one message"):
        _ = await rt.call(Encoder, user_input=rt.llm.MessageHistory([]))
    
@pytest.mark.asyncio
async def test_system_message_as_a_string_class_based(mock_llm):
    # if a string is provided as system_message in a class based initialization, we are throwing an error
    class Encoder(rt.library.TerminalLLM):
        def __init__(
                self,
                user_input: rt.llm.MessageHistory,
                llm_model: rt.llm.ModelBase = mock_llm(),
            ):
                user_input = [x for x in user_input if x.role != "system"]
                user_input.insert(0, "You are a helpful assistant that can encode text into bytes.")
                super().__init__(
                    user_input=MessageHistory(user_input),
                    llm_model=llm_model,
                )
        @classmethod
        def pretty_name(cls) -> str:
            return "Simple Node"

    with pytest.raises(NodeInvocationError, match="Message history must be a list of Message objects."):
        response = await rt.call(Encoder, user_input=rt.llm.MessageHistory([rt.llm.UserMessage("hello world")]))
# =================== END invocation exceptions =====================
# ================================================ END terminal_llm Exception testing ===========================================================
