import pytest
import requestcompletion as rc
from pydantic import BaseModel
from requestcompletion.llm import MessageHistory, SystemMessage, ModelBase, UserMessage, AssistantMessage, ToolMessage, ToolResponse
from requestcompletion.llm.response import Response
from requestcompletion.nodes.library import StructuredLLM, structured_llm
from requestcompletion.exceptions import NodeCreationError, NodeInvocationError
from typing import Type

# ===================================================== START Unit Testing =========================================================
@pytest.mark.asyncio
async def test_structured_llm_instantiate_and_invoke(simple_output_model, mock_llm, mock_structured_function):
    class MyLLM(StructuredLLM):

        @classmethod
        def schema(cls) -> Type[BaseModel]:
            return simple_output_model
        
        @classmethod
        def pretty_name(cls):
            return "Mock LLM"
    mh = MessageHistory([SystemMessage("system prompt"), UserMessage("hello")])
    result = await rc.call(MyLLM, message_history=mh, llm_model=mock_llm(structured=mock_structured_function))
    assert isinstance(result, simple_output_model)
    assert result.text == "dummy content"
    assert result.number == 42

def test_structured_llm_output_model_classmethod(simple_output_model):
    class MyLLM(StructuredLLM):
        @classmethod
        def schema(cls) -> Type[BaseModel]:
            return simple_output_model
    assert MyLLM.schema() is simple_output_model

@pytest.mark.asyncio
async def test_structured_llm_easy_usage_wrapper_invoke(simple_output_model, mock_llm, mock_structured_function):
    node = structured_llm(
        schema=simple_output_model,
        system_message="system prompt",
        llm_model=mock_llm(structured=mock_structured_function),
        pretty_name="TestNode"
    )
    mh = MessageHistory([UserMessage("hello")])
    result = await rc.call(node, message_history=mh)
    assert isinstance(result, simple_output_model)
    assert result.text == "dummy content"
    assert result.number == 42

def test_structured_llm_easy_usage_wrapper_classmethods(simple_output_model, mock_llm):
    node = structured_llm(
        schema=simple_output_model,
        system_message="system prompt",
        llm_model=mock_llm(),
        pretty_name="TestNode"
    )
    assert node.schema() is simple_output_model
    assert node.pretty_name() == "TestNode"
# ===================================================== END Unit Testing ===========================================================

# ================================================ START Exception testing ===========================================================
# =================== START Easy Usage Node Creation ===================
@pytest.mark.asyncio
async def test_easy_usage_no_output_model():
    with pytest.raises(NodeCreationError, match="Output model cannot be empty"):
        _ = rc.library.structured_llm(
            schema=None,
            system_message="You are a helpful assistant that can strucure the response into a structured output.",
            llm_model=rc.llm.OpenAILLM("gpt-4o"),
            pretty_name="Structured ToolCallLLM",
        )

@pytest.mark.asyncio
async def test_easy_usage_empty_output_model(empty_output_model):
    with pytest.raises(NodeCreationError, match="Output model cannot be empty"):
        _ = rc.library.structured_llm(
            schema=empty_output_model,
            system_message="You are a helpful assistant that can strucure the response into a structured output.",
            llm_model=rc.llm.OpenAILLM("gpt-4o"),
            pretty_name="Structured ToolCallLLM",
        )

@pytest.mark.asyncio
async def test_easy_usage_tool_details_not_provided(simple_output_model):
    with pytest.raises(
        NodeCreationError,
        match="Tool parameters are provided, but tool details are missing.",
    ):
        _ = rc.library.structured_llm(
            schema=simple_output_model,
            system_message="You are a helpful assistant that can strucure the response into a structured output.",
            llm_model=rc.llm.OpenAILLM("gpt-4o"),
            pretty_name="Structured ToolCallLLM",
            tool_params={
                rc.llm.Parameter(
                    name="text_input",
                    param_type="string",
                    description="A sentence to generate a response for.",
                )
            },
        )


@pytest.mark.asyncio
async def test_easy_usage_duplicate_parameter_names(simple_output_model):
    with pytest.raises(
        NodeCreationError, match="Duplicate parameter names are not allowed."
    ):
        _ = rc.library.structured_llm(
            schema=simple_output_model,
            system_message="You are a helpful assistant that can strucure the response into a structured output.",
            llm_model=rc.llm.OpenAILLM("gpt-4o"),
            pretty_name="Structured ToolCallLLM",
            tool_details="A tool that generates a structured response that includes word count.",
            tool_params={
                rc.llm.Parameter(
                    name="text_input",
                    param_type="string",
                    description="A sentence to generate a response for.",
                ),
                rc.llm.Parameter(
                    name="text_input",
                    param_type="string",
                    description="A duplicate parameter.",
                ),
            },
        )


@pytest.mark.asyncio
async def test_easy_usage_system_message_as_a_string(simple_output_model):
    Node_Class = rc.library.structured_llm(
        schema=simple_output_model,
        system_message="You are a helpful assistant that can structure the response into a structured output.",
        llm_model=rc.llm.OpenAILLM("gpt-4o"),
        pretty_name="Structured ToolCallLLM",
    )

    node = Node_Class(message_history=rc.llm.MessageHistory([]))
    assert all(isinstance(m, rc.llm.Message) for m in node.message_hist)
    assert node.message_hist[0].role == "system"


@pytest.mark.asyncio
async def test_system_message_as_a_user_message(simple_output_model):
    with pytest.raises(NodeCreationError, match="system_message must be of type string or SystemMessage, not any other type."):
        _ = rc.library.structured_llm(
            schema=simple_output_model,
            system_message=rc.llm.UserMessage("You are a helpful assistant that can structure the response into a structured output."),
            llm_model=rc.llm.OpenAILLM("gpt-4o"),
            pretty_name="Structured ToolCallLLM",
        )
# =================== END Easy Usage Node Creation ===================

# =================== START Class Based Node Creation ===================
@pytest.mark.asyncio
async def test_class_based_empty_output_model(empty_output_model):
    with pytest.raises(NodeCreationError, match="Output model cannot be empty."):
        class Structurer(rc.library.StructuredLLM):
            def __init__(
                self,
                message_history: rc.llm.MessageHistory,
                llm_model: rc.llm.ModelBase = None,
            ):
                message_history = [x for x in message_history if x.role != "system"]
                message_history.insert(0, rc.llm.SystemMessage("You are a helpful assistant."))
                super().__init__(
                    message_history=message_history,
                    llm_model=llm_model,
                )

            @classmethod
            def schema(cls) -> Type[BaseModel]:
                return empty_output_model
            
            @classmethod
            def pretty_name(cls) -> str:
                return "Structurer"

@pytest.mark.asyncio
async def test_class_based_output_model_not_class_based(simple_output_model):
    with pytest.raises(NodeCreationError, match="The 'schema' method must be a @classmethod."):
        class Structurer(rc.library.StructuredLLM):
            def __init__(
                self,
                message_history: rc.llm.MessageHistory,
                llm_model: rc.llm.ModelBase = None,
            ):
                message_history = [x for x in message_history if x.role != "system"]
                message_history.insert(0, rc.llm.SystemMessage("You are a helpful assistant."))
                super().__init__(
                    message_history=message_history,
                    llm_model=llm_model,
                )

            def schema(cls) -> Type[BaseModel]:
                return simple_output_model
            
            @classmethod
            def pretty_name(cls) -> str:
                return "Structurer"
            
@pytest.mark.asyncio
async def test_class_based_output_model_not_pydantic():
    with pytest.raises(NodeCreationError, match="Output model must be a pydantic model"):
        class Structurer(rc.library.StructuredLLM):
            def __init__(
                self,
                message_history: rc.llm.MessageHistory,
                llm_model: rc.llm.ModelBase = None,
            ):
                message_history = [x for x in message_history if x.role != "system"]
                message_history.insert(0, rc.llm.SystemMessage("You are a helpful assistant."))
                super().__init__(
                    message_history=message_history,
                    llm_model=llm_model,
                )

            @classmethod
            def schema(cls):
                return {"text": "hello world"}
            
            @classmethod
            def pretty_name(cls) -> str:
                return "Structurer"
# =================== END Class Based Node Creation =====================

# =================== START invocation exceptions =====================
@pytest.mark.asyncio
async def test_system_message_in_message_history_easy_usage(simple_output_model):
    with pytest.raises(NodeCreationError, match="system_message must be of type string or SystemMessage, not any other type."):
        simple_structured = rc.library.structured_llm(
            schema=simple_output_model,
            system_message=rc.llm.UserMessage("You are a helpful assistant that can structure the response into a structured output."),
            llm_model=rc.llm.OpenAILLM("gpt-4o"),
            pretty_name="Structured ToolCallLLM",
        )

@pytest.mark.asyncio
async def test_system_message_in_message_history_class_based(simple_output_model):
    class Structurer(rc.library.StructuredLLM):
        def __init__(
            self,
            message_history: rc.llm.MessageHistory,
            llm_model: rc.llm.ModelBase = None,
        ):
            message_history.insert(0, "You are a helpful assistant.")
            super().__init__(
                message_history=message_history,
                llm_model=llm_model,
            )

        @classmethod
        def schema(cls) -> Type[BaseModel]:
            return simple_output_model
        
        @classmethod
        def pretty_name(cls) -> str:
            return "Structurer"
        
    with pytest.raises(NodeInvocationError, match="Message history must be a list of Message objects."):
        await rc.call(Structurer, message_history=rc.llm.MessageHistory(["hello world"]))
# =================== END invocation exceptions =====================
# ================================================ END Exception testing =============================================================
