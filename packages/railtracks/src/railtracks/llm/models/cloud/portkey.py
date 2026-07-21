import os

from ...models.api_providers._openai_compatable_provider_wrapper import (
    OpenAICompatibleProvider,
)
from ...providers import ModelProvider
from ...retries import RetryApproach


class PortKeyLLM(OpenAICompatibleProvider):
    def __init__(
        self,
        model_name: str,
        *,
        api_key: str | None = None,
        temperature: float | None = None,
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
            api_base=portkey.base_url,
            api_key=portkey.api_key,
            temperature=temperature,
            retry_approach=retry_approach,
        )

    @classmethod
    def model_gateway(cls):
        return ModelProvider.PORTKEY

    def model_provider(self):
        # TODO: Implement specialized logic to determine the model provider
        return ModelProvider.PORTKEY
