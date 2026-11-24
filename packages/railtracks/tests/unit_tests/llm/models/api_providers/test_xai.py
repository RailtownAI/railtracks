import pytest
from railtracks.llm import (
    XAILLM,
    Attachment,
    AttachmentNotSupportedError,
    UserMessage,
)
from railtracks.llm.models._model_exception_base import ModelNotFoundError
from railtracks.llm.providers import ModelProvider


@pytest.mark.parametrize("model_name", ["grok-4.3", "xai/grok-4.3"])
def test_llm_correct_init(model_name):
    """The `xai/` prefix is optional and always routes through litellm's xAI provider."""
    model = XAILLM(model_name)

    assert model.model_name() == "xai/grok-4.3"
    assert model.model_provider() == ModelProvider.XAI


@pytest.mark.parametrize(
    "model_name", ["gpt-4o", "claude-sonnet-4-6", "xai/not-a-grok-model"]
)
def test_rejects_unknown_model(model_name):
    with pytest.raises(ModelNotFoundError):
        XAILLM(model_name)


@pytest.mark.parametrize(
    "attachment",
    [
        Attachment.from_bytes(b"%PDF-1.4", mime_type="application/pdf"),
        Attachment.from_bytes(b"wav", mime_type="audio/wav"),
        Attachment("https://example.com/clip.mp4"),
    ],
    ids=["pdf", "audio", "video"],
)
def test_rejects_non_image_attachments(attachment):
    """litellm's catalog lists vision, but no PDF or audio input, for Grok models."""
    message = UserMessage("Describe this.", attachment=attachment)

    with pytest.raises(AttachmentNotSupportedError, match=attachment.modality):
        XAILLM("grok-4.3")._to_litellm_message(message)
