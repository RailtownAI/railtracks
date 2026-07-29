import logging
from typing import List, Literal, TypeVar

from litellm.exceptions import InternalServerError

from ...history import MessageHistory
from ...providers import ModelProvider
from ...retries import RetryApproach
from ...tools import Tool
from .._litellm_wrapper import LiteLLMWrapper
from .._model_exception_base import ModelError

logger = logging.getLogger(__name__)

_TStream = TypeVar("_TStream", Literal[True], Literal[False])


class AzureAIError(ModelError):
    pass


class AzureAILLM(LiteLLMWrapper[_TStream]):
    """Azure Foundry LLM wrapper.

    Accepts either litellm prefix:
    - ``azure/<deployment>`` — Azure OpenAI Service route; the string after the
      slash is the user-chosen deployment name and can be anything.
    - ``azure_ai/<model>`` — Azure AI Foundry model-inference route; the string
      after the slash is a model identifier from Foundry's catalog.

    The model string is forwarded verbatim to litellm — no client-side validation
    is done against a static catalog, since deployment names are user-defined and
    can't be known ahead of time.
    """

    @classmethod
    def model_gateway(cls):
        return ModelProvider.AZUREAI

    def model_provider(self) -> ModelProvider:
        return self.model_gateway()

    def __init__(
        self,
        model_name: str,
        *,
        temperature: float | None = None,
        retry_approach: RetryApproach | None = None,
        **kwargs,
    ):
        """Initialize an Azure AI LLM instance.

        Args:
            model_name (str): Full litellm model string, e.g. ``azure/my-deployment``
                or ``azure_ai/deepseek-r1``. See the class docstring for the
                difference between the two prefixes.
            temperature (float | None, optional): Sampling temperature for generation (e.g. 0.0–2.0).
                If None, the provider default is used.
            **kwargs: Additional arguments passed to the parent LiteLLMWrapper.
        """
        super().__init__(
            model_name, temperature=temperature, retry_approach=retry_approach, **kwargs
        )
        self.logger = logger

    def chat(self, messages: MessageHistory):
        try:
            return super().chat(messages)
        except InternalServerError as e:
            raise AzureAIError(
                reason=f"Azure AI LLM error while processing the request: {e}"
            ) from e

    def chat_with_tools(self, messages: MessageHistory, tools: List[Tool]):
        try:
            return super().chat_with_tools(messages, tools)
        except InternalServerError as e:
            raise AzureAIError(
                reason=f"Azure AI LLM error while processing the request: {e}"
            ) from e
