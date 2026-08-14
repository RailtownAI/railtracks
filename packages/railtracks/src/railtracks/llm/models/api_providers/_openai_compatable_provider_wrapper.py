from abc import ABC
from typing import Any, Literal

from ...providers import ModelProvider
from ...retries import RetryApproach
from ._provider_wrapper import ProviderLLMWrapper


class OpenAICompatibleProvider(ProviderLLMWrapper, ABC):
    def __init__(
        self,
        model_name: str,
        *,
        api_base: str,
        api_key: str,
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        reasoning_effort: Literal["minimal", "low", "medium", "high"] | None = None,
        service_tier: str | None = None,
        verbosity: Literal["low", "medium", "high"] | None = None,
        retry_approach: RetryApproach | None = None,
        **kwargs: Any,
    ):
        """Initialize an OpenAI-compatible gateway LLM instance (e.g. via PortKey).

        See `ProviderLLMWrapper.__init__` for the full per-hyperparameter description
        of the common hyperparameters below (`top_p`, `max_tokens`, `frequency_penalty`,
        `presence_penalty`, `reasoning_effort`, `service_tier`, `verbosity`).

        Note:
            Gateway-style providers can't be reliably introspected by litellm, so
            neither per-model hyperparameter support nor mutual-exclusion checks run
            here (see `_validate_common_hyperparameter_support` override below) —
            every hyperparameter, valid or not, is passed straight through and any
            error surfaces from the gateway or upstream provider directly.
        """
        super().__init__(
            model_name,
            api_base=api_base,
            api_key=api_key,
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

    def full_model_name(self, model_name: str) -> str:
        return f"openai/{model_name}"

    @classmethod
    def model_gateway(cls) -> ModelProvider:
        return ModelProvider.UNKNOWN

    def _pre_init_provider_check(self, model_name: str):
        # For OpenAI compatible providers, we skip the provider check since there is no way to do it.
        return model_name

    def _validate_tool_calling_support(self):
        # For OpenAI compatible providers, we skip the tool calling support check since there is no way to do it.
        return

    def _validate_common_hyperparameter_support(self) -> None:
        # For OpenAI compatible providers, litellm can't reliably introspect
        # gateway-style providers, so we skip the common hyperparameter support check.
        return
