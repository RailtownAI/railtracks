import os
from typing import Literal, TypeVar

from railtracks.llm.models.api_providers._openai_compatable_provider_wrapper import (
    OpenAICompatibleProvider,
)
from railtracks.llm.providers import ModelProvider

_TStream = TypeVar("_TStream", Literal[True], Literal[False])


class PortKeyLLM(OpenAICompatibleProvider[_TStream]):
    def __init__(
        self, model_name: str, *, stream: _TStream = False, api_key: str | None = None
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
        )

    @classmethod
    def model_gateway(cls):
        return ModelProvider.PORTKEY

    def model_provider(self):
        # TODO: Implement specialized logic to determine the model provider
        return ModelProvider.PORTKEY
