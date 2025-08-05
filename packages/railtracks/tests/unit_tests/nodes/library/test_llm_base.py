import pytest

from railtracks.llm.response import Response
from railtracks.nodes.concrete import LLMBase, RequestDetails
import railtracks.llm as llm

class MockModelNode(LLMBase):

    @classmethod
    def name(cls) -> str:
        return "Mock Node"

    async def invoke(self) -> llm.Message:
        return self.llm_model.chat(self.message_hist).message
    
    def return_output(self):
        return

@pytest.mark.asyncio
async def test_hooks(mock_llm):
    example_message_history = llm.MessageHistory([
        llm.UserMessage(content="What is the meaning of life?"),
    ])
    response = "There is none."
    llm_model = mock_llm(chat=lambda x: Response(llm.AssistantMessage(response)))
    node = MockModelNode(
        llm_model=llm_model,
        user_input=example_message_history,

    )

    node_completion = await node.invoke()

    assert node_completion.content == response
    assert len(node.details["llm_details"]) == 1
    r_d = node.details["llm_details"][0]
    compare_request = RequestDetails(
            message_input=example_message_history,
            output=node_completion,
            model_name=llm_model.model_name(),
            model_provider=mock_llm.model_type(),
        )
    for i in zip(r_d.input, compare_request.input):
        assert i[0].role == i[1].role
        assert i[0].content == i[1].content

    assert r_d.output.role == compare_request.output.role
    assert r_d.output.content == compare_request.output.content
    assert r_d.model_name == compare_request.model_name
    assert r_d.model_provider == compare_request.model_provider



@pytest.mark.asyncio
async def test_error_hooks(mock_llm):
    example_message_history = llm.MessageHistory([
        llm.UserMessage(content="What is the meaning of life?"),
    ])
    exception = Exception("Simulated error")
    def exception_raiser(x):
        raise exception

    llm_model = mock_llm(chat=exception_raiser)
    node = MockModelNode(
        llm_model=llm_model,
        user_input=example_message_history,
    )

    with pytest.raises(Exception):
        await node.invoke()

    assert len(node.details["llm_details"]) == 1
    r_d = node.details["llm_details"][0]
    compare_request = RequestDetails(
            message_input=example_message_history,
            output=None,
            model_name=llm_model.model_name(),
            model_provider=mock_llm.model_type(),
        )

    for i in zip(r_d.input, compare_request.input):
        assert i[0].role == i[1].role
        assert i[0].content == i[1].content

    assert r_d.output is None
    assert r_d.model_name == compare_request.model_name
    assert r_d.model_provider == compare_request.model_provider


