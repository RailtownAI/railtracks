from polars import String
import pytest
import railtracks as rt
from railtracks.built_nodes.concrete.response import StringResponse
from railtracks.exceptions import NodeCreationError
from railtracks.llm import AssistantMessage, ToolCall
from railtracks.llm.response import Response
from typing import Generator


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
    @pytest.mark.parametrize("stream", [False, True])
    async def test_simple_tool(self, mock_llm, stream):
        def secret_phrase():
            rt.context.put("secret_phrase_called", True)
            return "Constantinople"

        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(name="secret_phrase", identifier="id_42424242", arguments={})
            ],
            stream=stream,
        )

        agent = rt.agent_node(
            tool_nodes={rt.function_node(secret_phrase)},
            name="Secret Phrase Maker",
            system_message="You are a helpful assistant that can call the tools available to you to answer user queries",
            llm=llm,
        )

        with rt.Session(logging_setting="NONE"):
            response = await rt.call(
                agent,
                user_input="What is the secret phrase? Only return the secret phrase, no other text.",
            )
            collected_response: StringResponse | None = None
            if stream:
                for chunk in response:
                    assert isinstance(chunk, (str, StringResponse))
                    if isinstance(chunk, StringResponse):
                        collected_response = chunk
            else:
                collected_response = response
            assert collected_response is not None
            assert "Constantinople" in collected_response.text
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
        with rt.Session(logging_setting="NONE"):
            _reset_tools_called()
            _ = await rt.call(agent, user_input=message)
            assert rt.context.get("tools_called") == 1
            _reset_tools_called()
            _ = await rt.call(agent, user_input=message)
            assert rt.context.get("tools_called") == 1

    def test_negative_tc(self, mock_llm):
        with pytest.raises(NodeCreationError):
            _ = rt.agent_node(
                tool_nodes={rt.function_node(lambda: 42)},
                name="Magic Number Agent",
                system_message="You are a helpful assistant that can call the tools available to you to answer user queries",
                llm=mock_llm(),
                max_tool_calls=-1,
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "num_tc , llm_requests_extra",
        [
            (0, False),
            (1, False),
            (5, False),
            (1, True),  # extra call requested by LLM, but tool call limit is 1
            (5, True),
        ],
        ids=["zero_exact", "one_exact", "five_exact", "one_extra", "five_extra"],
    )
    async def test_base_functionality(
        self,
        mock_llm,
        _reset_tools_called,
        _increment_tools_called,
        num_tc,
        llm_requests_extra,
    ):
        """Test tool calls when LLM requests exact or extra calls compared to max_tool_calls limit."""

        def magic_number():
            #  incrementing count for testing purposes
            _increment_tools_called()
            return 42

        llm_call_count = num_tc + (1 if llm_requests_extra else 0)
        llm = mock_llm(
            requested_tool_calls=[
                ToolCall(name="magic_number", identifier="id_42424242", arguments={})
                for _ in range(llm_call_count)
            ]
        )
        # =======================================

        agent = rt.agent_node(
            tool_nodes={rt.function_node(magic_number)},
            name="Magic Number Agent",
            system_message="You are a helpful assistant that can call the tools available to you to answer user queries",
            llm=llm,
            max_tool_calls=num_tc,
        )

        with rt.Session(logging_setting="NONE"):
            _reset_tools_called()
            response = await rt.call(
                agent, user_input=f"Get me {num_tc} magic numbers."
            )
            assert isinstance(response.content, str)
            assert rt.context.get("tools_called") == num_tc


@pytest.mark.asyncio
class TestStructuredToolCalling:
    async def test_base_functionality(self, mock_llm, simple_output_model):
        def secrets():
            rt.context.put("secrets_called", True)
            return ("Constantinople", 42)

        llm = mock_llm(
            custom_response='{"text": "Constantinople", "number": "42"}',  # for passing into schema
            requested_tool_calls=[
                ToolCall(name="secrets", identifier="id_42424242", arguments={})
            ],
        )

        agent = rt.agent_node(
            name="Secret Phrase Maker",
            system_message="You are a helpful assistant that can call the tools available to you to answer user queries",
            llm=llm,
            output_schema=simple_output_model,
            tool_nodes={rt.function_node(secrets)},
        )

        with rt.Session(logging_setting="NONE"):
            response = await rt.call(
                agent,
                user_input="What is the secret phrase? Only return the structured output, no other text.",
            )
            assert isinstance(response.content, simple_output_model)
            assert response.content.text == "Constantinople"
            assert response.content.number == 42
            assert rt.context.get("secrets_called")

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
        llm=mock_llm('{"text": "Successfully added 50 to 42 to get 92", "number": 92}'),
        output_schema=simple_output_model,
        max_tool_calls=3,
    )

        with rt.Session(name="AgentHandlerNode") as run:
            result =  await rt.call(AgentHandler, rt.llm.MessageHistory([
                rt.llm.UserMessage("Give me a number and add 50 to it please"),
                ]))
            
        print(result.content)
        assert isinstance(result.content, simple_output_model)
        assert isinstance(result.content.text, str)
        assert isinstance(result.content.number, int)
        assert result.content.text == "Successfully added 50 to 42 to get 92"
        assert result.content.number == 92
        

