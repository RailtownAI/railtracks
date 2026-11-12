import pytest
from railtracks.llm import (
    AnthropicLLM,
    Attachment,
    AttachmentNotSupportedError,
    UserMessage,
)


def test_llm_correct_init():
    """
    Test that AnthropicLLM initializes correctly with a valid model name.
    """
    model = AnthropicLLM("claude-sonnet-4-6")
    assert model is not None


@pytest.mark.parametrize(
    "attachment",
    [
        Attachment.from_bytes(b"wav", mime_type="audio/wav"),
        Attachment("https://example.com/clip.mp4"),
    ],
    ids=["audio", "video"],
)
def test_rejects_audio_and_video(attachment):
    """litellm's Anthropic transform drops `input_audio` parts, so they must raise."""
    message = UserMessage("Describe this.", attachment=attachment)

    with pytest.raises(AttachmentNotSupportedError, match=attachment.modality):
        AnthropicLLM("claude-sonnet-4-6")._to_litellm_message(message)
