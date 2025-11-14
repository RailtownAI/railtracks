from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from typing import (
    Any,
    Dict,
    Generator,
    Generic,
    Iterable,
    Literal,
    TypeVar,
)

from pydantic import BaseModel
from typing_extensions import Self

from railtracks.exceptions.errors import LLMError, NodeInvocationError
from railtracks.exceptions.messages.exception_messages import get_message
from railtracks.llm import (
    Message,
    MessageHistory,
    ModelBase,
    ModelProvider,
    Parameter,
    SystemMessage,
    UserMessage,
)
from railtracks.llm.response import Response
from railtracks.nodes.nodes import Node
from railtracks.prompts.prompt import inject_context
from railtracks.utils.logging import get_rt_logger
from railtracks.validation.node_invocation.validation import (
    check_llm_model,
    check_message_history,
)

from .response import LLMResponse, StringResponse, StructuredResponse

# Global logger for LLM nodes
logger = get_rt_logger("Node.LLM")

_T = TypeVar("_T")


class RequestDetails:
    """
    A named tuple to store details of each LLM request.
    """

    def __init__(
        self,
        message_input: MessageHistory,
        output: Message | None,
        model_name: str | None,
        model_provider: ModelProvider | None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_cost: float | None = None,
        system_fingerprint: str | None = None,
        latency: float | None = None,
    ):
        self.input = message_input
        self.output = output
        self.model_name = model_name
        self.model_provider = model_provider
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_cost = total_cost
        self.system_fingerprint = system_fingerprint
        self.latency = latency

    def __repr__(self):
        return f"RequestDetails(model_name={self.model_name}, model_provider={self.model_provider}, input={self.input}, output={self.output})"


_TStream = TypeVar("_TStream", Literal[True], Literal[False])
_TCollectedOutput = TypeVar("_TCollectedOutput", bound=LLMResponse)


class LLMBase(Node[_T], ABC, Generic[_T, _TCollectedOutput, _TStream]):
    """
    A basic LLM base class that encapsulates the attaching of an LLM model and message history object.

    The main functionality of the class is contained within the attachment of pre and post hooks to the model so we can
    store debugging details that will allow us to determine token usage.

    Args:
        user_input: The message history to use. Can be a MessageHistory object, a UserMessage object, or a string.
            If a string is provided, it will be converted to a MessageHistory with a UserMessage.
            If a UserMessage is provided, it will be converted to a MessageHistory.
            llm: The LLM model to use. If None, the default model will be used.
    """

    def __init__(
        self,
        user_input: MessageHistory | UserMessage | str | list[Message],
        llm: ModelBase[_TStream] | None = None,
    ):
        super().__init__()

        # Convert str or UserMessage to MessageHistory if needed
        if isinstance(user_input, str):
            user_input = MessageHistory([UserMessage(user_input)])
        elif isinstance(user_input, UserMessage):
            user_input = MessageHistory([user_input])
        elif isinstance(user_input, list) and not isinstance(
            user_input, MessageHistory
        ):
            user_input = MessageHistory(user_input)

        self._verify_message_history(user_input)
        message_history_copy = deepcopy(
            user_input
        )  # Ensure we don't modify the original message history

        # If there is a system_message method we add it to message history
        if self.system_message() is not None:
            if not isinstance(self.system_message(), (SystemMessage, str)):
                raise NodeInvocationError(
                    message=get_message("INVALID_SYSTEM_MESSAGE_MSG"),
                    fatal=True,
                )
            # If there is already a SystemMessage in MessageHistory we will tell user both are being used
            if len([x for x in message_history_copy if x.role == "system"]) > 0:
                logger.warning(
                    "System message was passed in message history and defined as a method. We will use both and add model method to message history."
                )
            message_history_copy.insert(
                0,
                (
                    SystemMessage(self.system_message())
                    if isinstance(self.system_message(), str)
                    else self.system_message()
                ),
            )

        instance_injected_llm_model = self.get_llm()

        if instance_injected_llm_model is not None:
            if llm is not None:
                logger.warning(
                    "You have provided an llm model as a parameter and as a class variable. We will use the parameter."
                )
                unwrapped_llm_model = llm
            else:
                unwrapped_llm_model = instance_injected_llm_model
        else:
            unwrapped_llm_model = llm

        self._verify_llm_model(unwrapped_llm_model)
        assert isinstance(unwrapped_llm_model, ModelBase), (
            "unwrapped_llm_model must be an instance of llm.ModelBase"
        )
        self.llm_model = unwrapped_llm_model

        self.message_hist = message_history_copy

        self._details["llm_details"] = []

        self._attach_llm_hooks()

    @classmethod
    def prepare_tool_message_history(
        cls, tool_parameters: Dict[str, Any], tool_params: Iterable[Parameter] = None
    ) -> MessageHistory:
        """
        Prepare a message history for a tool call with the given parameters.

        This method creates a coherent instruction message from tool parameters instead of
        multiple separate messages.

        Args:
            tool_parameters: Dictionary of parameter names to values
            tool_params: Iterable of Parameter objects defining the tool parameters

        Returns:
            MessageHistory object with a single UserMessage containing the formatted parameters
        """
        # If no parameters, return empty message history
        if not tool_params:
            return MessageHistory([])

        # Create a single, coherent instruction instead of multiple separate messages
        instruction_parts = [
            "You are being called as a tool with the following parameters:",
            "",
        ]

        for param in tool_params:
            value = tool_parameters[param.name]
            # Format the parameter appropriately based on its type
            if param.param_type == "array" and isinstance(value, list):
                formatted_value = ", ".join(str(v) for v in value)
                instruction_parts.append(f"• {param.name}: {formatted_value}")
            elif param.param_type == "object" and isinstance(value, dict):
                # For objects, show key-value pairs
                formatted_value = "; ".join(f"{k}={v}" for k, v in value.items())
                instruction_parts.append(f"• {param.name}: {formatted_value}")
            else:
                instruction_parts.append(f"• {param.name}: {value}")

        instruction_parts.extend(
            ["", "Please execute your function based on these parameters."]
        )

        # Create a single UserMessage with the complete instruction
        return MessageHistory([UserMessage("\n".join(instruction_parts))])

    @abstractmethod
    def return_output(self, message: Message | None = None) -> _TCollectedOutput: ...

    @classmethod
    def _verify_message_history(cls, message_history: MessageHistory):
        """Verify the message history is valid for this LLM."""
        check_message_history(message_history, cls.system_message())

    @classmethod
    def _verify_llm_model(cls, llm: ModelBase[_TStream] | None):
        """Verify the llm model is valid for this LLM."""
        check_llm_model(llm)

    @classmethod
    def get_llm(cls) -> ModelBase[_TStream] | None:
        return None

    @classmethod
    def system_message(cls) -> SystemMessage | str | None:
        return None

    def _attach_llm_hooks(self):
        """Attach pre and post hooks to the llm model."""
        self.llm_model.add_pre_hook(self._pre_llm_hook)
        self.llm_model.add_post_hook(self._post_llm_hook)
        self.llm_model.add_exception_hook(self._exception_llm_hook)

    def _detach_llm_hooks(self):
        """Detach pre and post hooks from the llm model."""
        self.llm_model.remove_pre_hooks()
        self.llm_model.remove_post_hooks()
        self.llm_model.remove_exception_hooks()

    def _pre_llm_hook(self, message_history: MessageHistory) -> MessageHistory:
        """Hook to modify messages before sending them to the llm model."""
        return inject_context(message_history)

    def _post_llm_hook(self, message_history: MessageHistory, response: Response):
        """Hook to store the response details after invoking the llm model."""

        output_message = deepcopy(response.message)

        self._details["llm_details"].append(
            RequestDetails(
                message_input=deepcopy(message_history),
                output=output_message,
                model_name=(
                    response.message_info.model_name
                    if response.message_info.model_name is not None
                    else self.llm_model.model_name()
                ),
                model_provider=self.llm_model.model_provider(),
                input_tokens=response.message_info.input_tokens,
                output_tokens=response.message_info.output_tokens,
                total_cost=response.message_info.total_cost,
                system_fingerprint=response.message_info.system_fingerprint,
                latency=response.message_info.latency,
            )
        )

        return response

    def _exception_llm_hook(
        self, message_history: MessageHistory, exception: Exception
    ):
        """Hook to store the response details after exception was thrown during llm model invocation"""
        self._details["llm_details"].append(
            RequestDetails(
                message_input=deepcopy(message_history),
                output=None,
                model_name=self.llm_model.model_name(),
                model_provider=self.llm_model.model_provider(),
            )
        )
        raise exception

    def return_into(self) -> str | None:
        """
        Return the name of the variable to return the result into. This method can be overridden by subclasses to
        customize the return variable name. By default, it returns None.

        Returns
        -------
        str
            The name of the variable to return the result into.
        """
        return None

    def format_for_return(self, result: _T) -> Any:
        """
        Format the result for return when return_into is provided. This method can be overridden by subclasses to
        customize the return format. By default, it returns None.

        Args:
            result (Any): The result to format.

        Returns:
            Any: The formatted result.
        """
        return None

    def format_for_context(self, result: _T) -> Any:
        """
        Format the result for context when return_into is provided. This method can be overridden by subclasses to
        customize the context format. By default, it returns the result as is.

        Args:
            result (Any): The result to format.

        Returns:
            Any: The formatted result.
        """
        return result

    def safe_copy(self) -> Self:
        new_instance: LLMBase = super().safe_copy()

        # This has got to be one of the weirdest things I've seen working with python
        # basically if we don't reattach the hooks, the `self` inserted into the model hooks will be the old memory address
        # so those updates will go to the old instance instead of the new one.
        new_instance._detach_llm_hooks()
        new_instance._attach_llm_hooks()
        # now that we have reattached the correct memory address to the llm the hooks will update properly.

        return new_instance

    @classmethod
    def type(cls):
        return "Agent"

    def _gen_wrapper(
        self, returned_mess: Generator[str | Response, None, Response]
    ) -> Generator[str | _TCollectedOutput, None, _TCollectedOutput]:
        for r in returned_mess:
            if isinstance(r, Response):
                message = r.message

                self._handle_output(message)
                response = self.return_output(message)
                yield response
                return response
            elif isinstance(r, str):
                yield r
            else:
                raise LLMError(
                    reason=f"ModelLLM returned unexpected type in generator. Expected str or Response, got {type(r)}",
                    message_history=self.message_hist,
                )

        raise LLMError(
            reason="The generator did not yield a final Response object",
            message_history=self.message_hist,
        )

    def _handle_output(self, output: Message):
        if output.role != "assistant":
            raise LLMError(
                reason="ModelLLM returned an unexpected message type.",
                message_history=self.message_hist,
            )

        self.message_hist.append(output)


_TStructured = TypeVar("_TStructured", bound=BaseModel)


class StructuredOutputMixIn(Generic[_TStructured]):
    message_hist: MessageHistory

    @classmethod
    @abstractmethod
    def output_schema(cls) -> type[_TStructured]:
        pass

    def return_output(
        self, message: Message | None = None
    ) -> StructuredResponse[_TStructured]:
        if message is None:
            message = self.message_hist[-1]

        content = message.content

        assert isinstance(content, self.output_schema()), (
            f"The final output must be a pydantic {self.output_schema()} or Stream instance. Instead it was {type(content)}"
        )

        return StructuredResponse(
            content=content,
            message_history=self.message_hist.removed_system_messages(),
        )


class StringOutputMixIn:
    message_hist: MessageHistory

    def return_output(self, message: Message | None = None) -> StringResponse:
        """Returns the String response."""
        if (
            message is None
        ):  # if no message is provided, use the last message from message history
            message = self.message_hist[-1]

        assert isinstance(message.content, str), "The final output must be a string"
        return StringResponse(
            content=message.content,
            message_history=self.message_hist.removed_system_messages(),
        )
