import os
import requests

import litellm

from .._litellm_wrapper import LiteLLMWrapper
from src.requestcompletion.utils.logging.create import get_rc_logger

LOGGER_NAME = "OLLAMA"


class OllamaException(Exception):
    pass


class Ollama(LiteLLMWrapper):
    @classmethod
    def model_type(cls):
        return "Ollama"

    def __init__(self, model_name: str, **kwargs):
        super().__init__(model_name, **kwargs)
        self.domain = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.logger = get_rc_logger(LOGGER_NAME)
        self.model_name = model_name.rsplit("/", 1)[-1]

        try:
            models = self._run_check("api/tags")
            model_names = {model["name"] for model in models["models"]}

            if self.model_name not in model_names:
                error_msg = f"{model_name} not available on server {self.domain}. Avaiable models are: {model_names}"
                raise OllamaException(error_msg)
        except Exception as e:
            raise Exception(f"The following error occured: {e}")

    def _run_check(self, endpoint: str):
        url = f"{self.domain}/{endpoint.lstrip('/')}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.critical(f"Failed to reach {url}")
            raise

    def chat_with_tools(self, messages, tools, **kwargs):
        if not litellm.supports_function_calling(model=self._model_name):
            raise ValueError(f"Model '{self.model_name}' does not support function calling.")

        return super().chat_with_tools(messages, tools, **kwargs)
