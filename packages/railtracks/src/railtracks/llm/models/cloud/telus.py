import os

from ..api_providers._openai_compatable_provider_wrapper import OpenAICompatibleProviderWrapper

class TelusLLM(OpenAICompatibleProviderWrapper):
    def __init__(self, model_name: str, api_base: str, api_key: str | None = None):
        # we need to map the telus API key to the OpenAI API key
        if api_key is None:
            try:
                api_key = os.environ["TELUS_API_KEY"]
            except KeyError as e:
                raise KeyError("Please set the TELUS_API_KEY environment variable to call the Telus API.") from e

        super().__init__(model_name=model_name, api_base=api_base, api_key=api_key)
    
    @classmethod
    def model_type(cls) -> str:
        return "Telus"
    
    
    
