
import pytest
import railtracks as rt
from railtracks.exceptions import NodeCreationError
from railtracks.llm import AssistantMessage, ToolCall
from railtracks.llm.response import Response


# NOTE: Simple successful tool calls are already tested in test_function.py
class TestSimpleToolCalling:
    @pytest.mark.skip("empty tool_nodes gives out terminal LLM. TODO: fix this")
    @pytest.mark.asyncio
    async def test_empty_tool_nodes(self, mock_llm):
        """Test when the output model is empty while making a node with easy wrapper."""
        with pytest.raises(
            NodeCreationError, match="tool_nodes must not return an empty set."
        ):
            _ = rt.agent_node(
                tool_nodes=set(),
                system_message="You are a helpful assistant that can strucure the response into a structured output.",
                llm=mock_llm(),
                name="ToolCallLLM",
            )

    @pytest.mark.asyncio
    async def test_simple_tool(self, mock_llm):
        def secret_phrase():
            rt.context.put("secret_phrase_called", True)
            return "Constantinople"

        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(name="secret_phrase", identifier="id_42424242", arguments={})
            ],
        )

        agent = rt.agent_node(
            tool_nodes={rt.function_node(secret_phrase)},
            name="Secret Phrase Maker",
            system_message="You are a helpful assistant that can call the tools available to you to answer user queries",
            llm=llm,
        )

        with rt.Session():
            response = await rt.call(
                agent,
                user_input="What is the secret phrase? Only return the secret phrase, no other text.",
            )
            assert response is not None
            assert "Constantinople" in response.text
            assert rt.context.get("secret_phrase_called")
            



class TestLimitedToolCalling:
    @pytest.mark.asyncio
    async def test_context_reset_between_runs(
        self, mock_llm, _reset_tools_called, _increment_tools_called
    ):
        def magic_number():
            #  incrementing count for testing purposes
            _increment_tools_called()
            return 42

        # ============ mock llm config =========
        def invoke_tool(messages, tools):
            assert len(tools) == 1
            assert tools[0].name == "magic_number"
            tool_response = magic_number()
            return Response(
                message=AssistantMessage(
                    str(tool_response),
                ),
            )

        llm = mock_llm()
        llm._chat_with_tools = invoke_tool
        # =======================================

        agent = rt.agent_node(
            tool_nodes={rt.function_node(magic_number)},
            name="Magic Number Agent",
            system_message="You are a helpful assistant that can call the tools available to you to answer user queries",
            llm=llm,
        )

        message = "Get the magic number and divide it by 2."
        with rt.Session():
            _reset_tools_called()
            _ = await rt.call(agent, user_input=message)
            assert rt.context.get("tools_called") == 1
            _reset_tools_called()
            _ = await rt.call(agent, user_input=message)
            assert rt.context.get("tools_called") == 1

class TestFunctionNodeCallWithFunctionList:
    @pytest.mark.asyncio
    async def test_function_node_call_with_function_list_parameter(
        self, mock_llm, simple_output_model
    ):
        def get_number() -> int:
            """
            Returns the number 42
            """
            return 42

        def add_value(number: int, value: int) -> int:
            """
            Adds 50 to a number and returns the result
            """

            return number + value

        tool_nodes = rt.function_node([get_number, add_value])

        AgentHandler = rt.agent_node(
        name="Random Number Generator Agent",
        tool_nodes=tool_nodes,
        system_message="""You are a number generator agent that can generate numbers and add a value to it""",
        llm=mock_llm( "Successfully added 50 to 42 to get 92",),
    )

        with rt.Session(name="AgentHandlerNode") as run:
            result =  await rt.call(AgentHandler, rt.llm.MessageHistory([
                rt.llm.UserMessage("Give me a number and add 50 to it please"),
                ]))
            
        assert "92" in result.content
        

