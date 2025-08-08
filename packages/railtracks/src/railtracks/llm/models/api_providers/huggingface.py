from ._provider_wrapper import ProviderLLMWrapper
from .._model_exception_base import ModelError


class HuggingFaceLLM(ProviderLLMWrapper):
    
    def pre_init_provider_check(self, model_name):
        # for huggingface models there is no good way of using `get_llm_provider` to check if the model is valid.
        # so we are just goinog to add `huggingface/` to the model name in case it is not there.
        # if the model name happens to be invalid, the error will be generated at runtime during `litellm.completion`. See `_litellm_wrapper.py`
        if model_name.startswith(self.model_type().lower()):
            model_name = "/".join(model_name.split("/")[1:])
            try:
                assert len(model_name.split("/")) == 3, "Invalid model name"
            except AssertionError as e:
                raise HUggingFaceModelNameingError(
                    reason=e.args[0],
                    notes=[
                        "Model name muust be of the format `huggingface/<provider>/<hf_org_or_user>/<hf_model>` or `<provider>/<hf_org_or_user>/<hf_model>`",
                        "We only support the huggingface Serverless Inference Provider Models.",
                        "Provider List: https://docs.litellm.ai/docs/providers",
                    ],
                )
        return model_name
    
    def _chat_with_tools_handler_base(self, messages, tools, **kwargs):
        # similar issue here, due to the wide range of huggingface models, `litellm.supports_function_calling` isn't always accurate.
        # so we are just going to pass through the check and the error will be generated at runtime during `litellm.completion`.
        pass

    
    @classmethod
    def model_type(cls) -> str:
        return "HuggingFace"

class HUggingFaceModelNameingError(ModelError):
    def __init__(self, reason: str, notes: list[str] = None):
        self.reason = reason
        self.notes = notes or []
        super().__init__(reason)

    def __str__(self):
        base = super().__str__()
        if self.notes:
            notes_str = (
                "\n"
                + self._color("Tips to debug:\n", self.GREEN)
                + "\n".join(self._color(f"- {note}", self.GREEN) for note in self.notes)
            )
            return f"\n{self._color(base, self.RED)}{notes_str}"
        return self._color(base, self.RED)