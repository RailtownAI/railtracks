import logging
from typing import List, Literal

from litellm.exceptions import InternalServerError

from railtracks.utils.deprecation import warn_pending_change

from ...history import MessageHistory
from ...providers import ModelProvider
from ...retries import RetryApproach
from ...tools import Tool
from .._litellm_wrapper import LiteLLMWrapper
from .._model_exception_base import ModelError

logger = logging.getLogger(__name__)


class AzureAIError(ModelError):
    pass


class AzureAILLM(LiteLLMWrapper):
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
        top_p: float | None = None,
        max_tokens: int | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        reasoning_effort: Literal["none", "minimal", "low", "medium", "high"]
        | None = None,
        service_tier: str | None = None,
        verbosity: Literal["low", "medium", "high"] | None = None,
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
            top_p (float | None, optional): Nucleus sampling threshold.
            max_tokens (int | None, optional): Maximum tokens to generate.
            frequency_penalty (float | None, optional): Penalizes tokens by how often
                they've already appeared.
            presence_penalty (float | None, optional): Penalizes tokens that have
                already appeared at all.
            reasoning_effort (Literal["none", "minimal", "low", "medium", "high"] | None, optional):
                Requested reasoning effort for reasoning-capable models.
            service_tier (str | None, optional): Requested service tier. Provider-specific.
            verbosity (Literal["low", "medium", "high"] | None, optional): Requested
                output verbosity for models that support it.
            retry_approach (RetryApproach | None, optional): Retry strategy for transient
                failures.
            **kwargs: Additional arguments passed to the parent LiteLLMWrapper.

        Raises:
            AzureAIError: If the specified model is not available or if there are issues with the Azure AI service.
        """
        if kwargs.get("stream"):
            warn_pending_change(
                "Constructing a model with `stream=True`",
                change="is removed",
                instead="rt.astream(agent, ...) to stream an agent run",
                detail=(
                    "Streaming becomes async in 1.5.0: per-call model methods "
                    "(astream_chat, astream_chat_with_tools, astream_structured) "
                    "replace the streamed return value of chat()."
                ),
            )

        super().__init__(
            model_name,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            reasoning_effort=reasoning_effort,
            service_tier=service_tier,
            verbosity=verbosity,
            retry_approach=retry_approach,
            **kwargs,
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
