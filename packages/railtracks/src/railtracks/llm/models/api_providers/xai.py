import litellm

from ...providers import ModelProvider
from .._model_exception_base import ModelNotFoundError
from ._provider_wrapper import ProviderLLMWrapper


class XAILLM(ProviderLLMWrapper):
    """
    A wrapper that provides access to xAI's Grok models.
    """

    # litellm's catalog lists vision but no PDF or audio input for Grok models.
    _ACCEPTED_MODALITIES = frozenset({"image"})

    def _pre_init_provider_check(self, model_name: str) -> str:
        # litellm only resolves Grok names with the `xai/` prefix, so the base check can't be used.
        model_name = model_name.removeprefix("xai/")
        if f"xai/{model_name}" not in litellm.xai_models:
            raise ModelNotFoundError(
                reason=f"Please check the model name: {model_name}.",
                notes=[
                    "Model name must be a part of the model list.",
                    "Check the model list for the provider you are using.",
                    "Provider List: https://docs.litellm.ai/docs/providers",
                ],
            )
        return model_name

    @classmethod
    def model_gateway(cls) -> ModelProvider:
        return ModelProvider.XAI
