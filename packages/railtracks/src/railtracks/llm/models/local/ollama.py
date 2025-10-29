import os
from typing import Literal, TypeVar

import requests
from litellm.utils import supports_function_calling

from ...logging import setup_logger
from ...providers import ModelProvider
from .._litellm_wrapper import LiteLLMWrapper
from .._model_exception_base import FunctionCallingNotSupportedError, ModelError

LOGGER_NAME = "OLLAMA"
logger = setup_logger(__name__)

DEFAULT_DOMAIN = "http://localhost:11434"

_TStream = TypeVar("_TStream", Literal[True], Literal[False])


class OllamaError(ModelError):
    def __init__(self, reason: str):
        super().__init__(reason=reason)


class OllamaLLM(LiteLLMWrapper[_TStream]):
    def __init__(
        self,
        model_name: str,
        domain: Literal["default", "auto", "custom"] = "default",
        custom_domain: str | None = None,
        **kwargs,
    ):
        """Initialize an Ollama LLM instance.

        Args:
            model_name (str): Name of the Ollama model to use.
            domain (Literal["default", "auto", "custom"], optional): The domain configuration mode.
                - "default": Uses the default localhost domain (http://localhost:11434)
                - "auto": Uses the OLLAMA_HOST environment variable, raises OllamaError if not set
                - "custom": Uses the provided custom_domain parameter, raises OllamaError if not provided
                Defaults to "default".
            custom_domain (str | None, optional): Custom domain URL to use when domain is set to "custom".
                Must be provided if domain="custom". Defaults to None.
            **kwargs: Additional arguments passed to the parent LiteLLMWrapper.

        Raises:
            OllamaError: If:
                - domain is "auto" and OLLAMA_HOST environment variable is not set
                - domain is "custom" and custom_domain is not provided
                - specified model is not available on the server
            RequestException: If connection to Ollama server fails
        """
        if not model_name.startswith("ollama/"):
            logger.warning(
                f"Prepending 'ollama/' to model name '{model_name}' for Ollama"
            )
            model_name = f"ollama/{model_name}"
        super().__init__(model_name, **kwargs)

        match domain:
            case "default":
                self.domain = DEFAULT_DOMAIN
            case "auto":
                domain_from_env = os.getenv("OLLAMA_HOST")
                if domain_from_env is None:
                    raise OllamaError("OLLAMA_HOST environment variable not set")
                self.domain = domain_from_env
            case "custom":
                if custom_domain is None:
                    raise OllamaError(
                        "Custom domain must be provided when domain is set to 'custom'"
                    )
                self.domain = custom_domain

        self._run_check(
            "api/tags"
        )  # This will crash the workflow if Ollama is not setup properly

    def _run_check(self, endpoint: str):
        url = f"{self.domain}/{endpoint.lstrip('/')}"
        try:
            response = requests.get(url)
            response.raise_for_status()

            models = response.json()

            model_names = {model["name"] for model in models["models"]}

            model_name = self.model_name().rsplit("/", 1)[
                -1
            ]  # extract the model name if the provider is also included

            if model_name not in model_names:
                error_msg = f"{self.model_name()} not available on server {self.domain}. Avaiable models are: {model_names}"
                logger.error(error_msg)
                raise OllamaError(error_msg)

        except OllamaError as e:
            logger.error(e)
            raise

        except requests.exceptions.RequestException as e:
            logger.error(e)
            raise

    def chat_with_tools(self, messages, tools, **kwargs):
        if not supports_function_calling(model=self._model_name):
            raise FunctionCallingNotSupportedError(self._model_name)

        return super().chat_with_tools(messages, tools, **kwargs)

    @classmethod
    def model_gateway(cls):
        return ModelProvider.OLLAMA

    def model_provider(self) -> ModelProvider:
        return super().model_provider()
