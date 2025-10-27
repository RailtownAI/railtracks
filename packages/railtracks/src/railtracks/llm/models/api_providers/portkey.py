from railtracks.llm.models.api_providers._openai_compatable_provider_wrapper import OpenAICompatibleProviderWrapper


class PortKey(OpenAICompatibleProviderWrapper):
    
    @classmethod
    def model_type(cls):
        return model