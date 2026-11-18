import pytest
from railtracks.llm import (
    Attachment,
    AttachmentNotSupportedError,
    OpenAILLM,
    UserMessage,
)


def test_llm_correct_init():
    """
    Test that OpenAI initializes correctly with a valid model name.
    """
    model = OpenAILLM("gpt-4o")
    assert model is not None


def test_sends_audio_and_rejects_video():
    model = OpenAILLM("gpt-4o")
    audio = UserMessage(
        "Transcribe.", attachment=Attachment.from_bytes(b"wav", mime_type="audio/wav")
    )
    video = UserMessage(
        "Describe.", attachment=Attachment("https://example.com/clip.mp4")
    )

    assert model._to_litellm_message(audio)["content"][1]["type"] == "input_audio"
    with pytest.raises(AttachmentNotSupportedError, match="not video"):
        model._to_litellm_message(video)
