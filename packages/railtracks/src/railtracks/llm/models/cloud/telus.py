import os

from ...providers import ModelProvider
from ...retries import RetryApproach
from ..api_providers._openai_compatable_provider_wrapper import OpenAICompatibleProvider


class TelusLLM(OpenAICompatibleProvider):
    def __init__(
        self,
        model_name: str,
        *,
        api_base: str,
        api_key: str | None = None,
        temperature: float | None = None,
        retry_approach: RetryApproach | None = None,
    ):
        # we need to map the telus API key to the OpenAI API key
        if api_key is None:
            try:
                api_key = os.environ["TELUS_API_KEY"]
            except KeyError as e:
                raise KeyError(
                    "Please set the TELUS_API_KEY environment variable to call the Telus API."
                ) from e

        super().__init__(
            model_name=model_name,
            api_base=api_base,
            api_key=api_key,
            temperature=temperature,
            retry_approach=retry_approach,
        )

    @classmethod
    def model_gateway(cls):
        return ModelProvider.TELUS
