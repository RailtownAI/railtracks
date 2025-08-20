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
    llm_model = mock_llm(response)
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

    llm_model = mock_llm()
    llm_model._chat = exception_raiser
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


@pytest.mark.asyncio
async def test_exception_hooks_detached_on_safe_copy(mock_llm):
    """Test that exception hooks are properly detached during safe_copy operation."""
    example_message_history = llm.MessageHistory([
        llm.UserMessage(content="What is the meaning of life?"),
    ])
    response = "There is none."
    llm_model = mock_llm(llm.AssistantMessage(response))
    
    # Create initial node
    original_node = MockModelNode(
        llm_model=llm_model,
        user_input=example_message_history,
    )
    
    # Verify hooks are initially attached (3 hooks: pre, post, exception)
    assert len(original_node.llm_model._pre_hooks) == 1
    assert len(original_node.llm_model._post_hooks) == 1
    assert len(original_node.llm_model._exception_hooks) == 1
    
    # Create a safe copy
    copied_node = original_node.safe_copy()
    
    # Verify that the copied node has its own hooks attached
    assert len(copied_node.llm_model._pre_hooks) == 1
    assert len(copied_node.llm_model._post_hooks) == 1
    assert len(copied_node.llm_model._exception_hooks) == 1
    
    # Verify the hooks are different objects (new instance hooks)
    assert copied_node.llm_model._pre_hooks[0] != original_node.llm_model._pre_hooks[0]
    assert copied_node.llm_model._post_hooks[0] != original_node.llm_model._post_hooks[0]
    assert copied_node.llm_model._exception_hooks[0] != original_node.llm_model._exception_hooks[0]


@pytest.mark.asyncio 
async def test_detach_hooks_removes_all_hook_types(mock_llm):
    """Test that _detach_llm_hooks removes all types of hooks including exception hooks."""
    example_message_history = llm.MessageHistory([
        llm.UserMessage(content="What is the meaning of life?"),
    ])
    response = "There is none."
    llm_model = mock_llm(llm.AssistantMessage(response))
    
    # Create node which automatically attaches hooks
    node = MockModelNode(
        llm_model=llm_model,
        user_input=example_message_history,
    )
    
    # Verify hooks are attached
    assert len(node.llm_model._pre_hooks) == 1
    assert len(node.llm_model._post_hooks) == 1
    assert len(node.llm_model._exception_hooks) == 1
    
    # Detach hooks
    node._detach_llm_hooks()
    
    # Verify all hooks are detached
    assert len(node.llm_model._pre_hooks) == 0
    assert len(node.llm_model._post_hooks) == 0
    assert len(node.llm_model._exception_hooks) == 0


