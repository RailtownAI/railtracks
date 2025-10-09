from ..providers import ModelProvider
from ._provider_wrapper import ProviderLLMWrapper
import json
from typing import Any, List, Dict, Optional
import re
import litellm

class CohereLLM(ProviderLLMWrapper):
    """
    A wrapper that provides access to the Cohere API.
    """

    @classmethod
    def model_type(cls) -> str:
        return ModelProvider.COHERE
