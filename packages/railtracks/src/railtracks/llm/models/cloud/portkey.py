import os
from typing import Literal, TypeVar

from ...models.api_providers._openai_compatable_provider_wrapper import (
    OpenAICompatibleProvider,
)
from ...providers import ModelProvider, ReasoningEffort
from ...retries import RetryApproach

_TStream = TypeVar("_TStream", Literal[True], Literal[False])


class PortKeyLLM(OpenAICompatibleProvider[_TStream]):
    def __init__(
        self,
        model_name: str,
        *,
        stream: _TStream = False,
        api_key: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        reasoning_effort: ReasoningEffort | str | None = None,
        service_tier: str | None = None,
        verbosity: Literal["low", "medium", "high"] | str | None = None,
        retry_approach: RetryApproach | None = None,
    ):
        try:
            from portkey_ai import Portkey
        except ImportError:
            raise ImportError(
                "Could not import portkey_ai package. Use railtracks[portkey]"
            )

        if api_key is None:
            try:
                api_key = os.environ["PORTKEY_API_KEY"]
            except KeyError:
                raise KeyError("Please set your PORTKEY_API_KEY in your .env file.")

        portkey = Portkey(api_key=api_key)

        super().__init__(
            model_name,
            stream=stream,
            api_base=portkey.base_url,
            api_key=portkey.api_key,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            reasoning_effort=reasoning_effort,
            service_tier=service_tier,
            verbosity=verbosity,
            retry_approach=retry_approach,
        )

    @classmethod
    def model_gateway(cls):
        return ModelProvider.PORTKEY

    def model_provider(self):
        # TODO: Implement specialized logic to determine the model provider
        return ModelProvider.PORTKEY
