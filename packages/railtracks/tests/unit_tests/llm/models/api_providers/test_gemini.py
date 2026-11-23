from litellm.llms.vertex_ai.gemini.transformation import (
    _gemini_convert_messages_with_history,
)
from railtracks.llm import Attachment, GeminiLLM, UserMessage


def test_llm_correct_init():
    """
    Test that GeminiLLM initializes correctly with a valid model name.
    """
    model = GeminiLLM("gemini-2.5-flash")
    assert model is not None


def test_every_modality_reaches_gemini_parts():
    """Pins litellm's Gemini transform: a URL in `file_data` becomes a file URI."""
    message = GeminiLLM("gemini-2.5-flash")._to_litellm_message(
        UserMessage(
            "Describe these.",
            attachment=[
                Attachment("https://example.com/clip.mp4"),
                Attachment.from_bytes(b"wav", mime_type="audio/wav"),
                Attachment.from_bytes(b"hello", mime_type="text/plain"),
            ],
        )
    )

    (content,) = _gemini_convert_messages_with_history(messages=[message])

    assert content["parts"][1:] == [
        {
            "file_data": {
                "mime_type": "video/mp4",
                "file_uri": "https://example.com/clip.mp4",
            }
        },
        {"inline_data": {"data": "d2F2", "mime_type": "audio/wav"}},
        {"inline_data": {"data": "aGVsbG8=", "mime_type": "text/plain"}},
    ]
