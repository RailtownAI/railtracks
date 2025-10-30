from typing import Literal, TypeVar

from ...providers import ModelProvider
from .._model_exception_base import ModelNotFoundError
from ._provider_wrapper import ProviderLLMWrapper

_TStream = TypeVar("_TStream", Literal[True], Literal[False])


class HuggingFaceLLM(ProviderLLMWrapper[_TStream]):
    def _pre_init_provider_check(self, model_name):
        """called by __init__ before the super call in ProviderLLMWrapper"""
        # for huggingface models there is no good way of using `get_llm_provider` to check if the model is valid.
        # so we are just goinog to add `huggingface/` to the model name in case it is not there.
        # if the model name happens to be invalid, the error will be generated at runtime during `litellm.completion`. See `_litellm_wrapper.py`
        if model_name.startswith(self.model_provider().lower()):
            model_name = "/".join(model_name.split("/")[1:])
        try:
            assert len(model_name.split("/")) == 3, "Invalid model name"
        except AssertionError as e:
            raise ModelNotFoundError(
                reason=e.args[0],
                notes=[
                    "Model name must be of the format `huggingface/<provider>/<hf_org_or_user>/<hf_model>` or `<provider>/<hf_org_or_user>/<hf_model>`",
                    "We only support the huggingface Serverless Inference Provider Models.",
                    "Provider List: https://docs.litellm.ai/docs/providers",
                ],
            )
        return model_name

    def model_provider(self) -> ModelProvider:
        # TODO implement logic for all the possible providers attached the hugging face.
        return ModelProvider.HUGGINGFACE

    def _validate_tool_calling_support(self):
        # NOTE: special exception case for huggingface
        # Due to the wide range of huggingface models, `litellm.supports_function_calling` isn't always accurate.
        # so we are just going to skip the check and the error (if any) will be generated at runtime during `litellm.completion`.
        pass

    @classmethod
    def model_gateway(cls):
        return ModelProvider.HUGGINGFACE
