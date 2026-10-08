"""DecisionState: text plus image attachments, sent as OpenAI-shape input."""

import base64

import httpx
import pytest
import railtracks as rt
from railtracks.decisions import (
    DecisionProviderRequestError,
    DecisionState,
    OpenAIDecisions,
    OpenRouterAI,
    TypeSafeAI,
)
from railtracks.decisions.transport._wire import to_input

from .conftest import Triage

# a 1x1 transparent PNG
PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAA"
    "AABJRU5ErkJggg=="
)
PNG_DATA_URL = f"data:image/png;base64,{PNG_B64}"


@pytest.fixture
def png(tmp_path):
    path = tmp_path / "cat.png"
    path.write_bytes(base64.b64decode(PNG_B64))
    return str(path)


def test_exported_from_rt_decisions():
    assert rt.decisions.DecisionState is DecisionState


class TestAttachments:
    def test_local_file_becomes_a_data_url(self, png):
        state = DecisionState(attachments=png)
        assert state.image_urls == (PNG_DATA_URL,)
        assert state.attachments == (png,)

    def test_url_is_passed_through(self):
        state = DecisionState(attachments="https://example.com/cat.jpg")
        assert state.image_urls == ("https://example.com/cat.jpg",)

    @pytest.mark.parametrize("source", [PNG_DATA_URL, PNG_B64], ids=["uri", "base64"])
    def test_data_uri_or_base64_becomes_a_data_url(self, source):
        assert DecisionState(attachments=source).image_urls == (PNG_DATA_URL,)

    def test_list_keeps_order(self, png):
        state = DecisionState(attachments=[png, "https://example.com/b.jpg"])
        assert state.image_urls == (PNG_DATA_URL, "https://example.com/b.jpg")

    def test_missing_file_rejected(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="nope.png"):
            DecisionState(attachments=str(tmp_path / "nope.png"))

    def test_non_image_file_rejected(self, tmp_path):
        path = tmp_path / "notes.png"
        path.write_text("not an image")
        with pytest.raises(ValueError, match="not a supported image"):
            DecisionState(attachments=str(path))

    def test_pdf_data_uri_rejected(self):
        pdf = "data:application/pdf;base64," + base64.b64encode(b"%PDF-1.4").decode()
        with pytest.raises(ValueError, match="images"):
            DecisionState(attachments=pdf)

    def test_needs_text_or_an_attachment(self):
        with pytest.raises(ValueError, match="text, an attachment"):
            DecisionState()
        with pytest.raises(ValueError, match="text, an attachment"):
            DecisionState(text="", attachments=[])

    def test_non_string_attachment_rejected(self):
        with pytest.raises(TypeError, match="attachments"):
            DecisionState(attachments=[1])  # type: ignore[list-item]


class TestInput:
    def test_text_only_is_plain_text(self):
        assert to_input(DecisionState(text="Help!")) == "Help!"

    def test_text_and_images_are_one_user_message(self, png):
        state = DecisionState(
            text="Which animal?", attachments=[png, "https://example.com/b.jpg"]
        )
        assert to_input(state) == [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Which animal?"},
                    {"type": "input_image", "image_url": PNG_DATA_URL},
                    {"type": "input_image", "image_url": "https://example.com/b.jpg"},
                ],
            }
        ]

    def test_images_only_have_no_text_part(self, png):
        [message] = to_input(DecisionState(attachments=png))
        assert message["content"] == [
            {"type": "input_image", "image_url": PNG_DATA_URL}
        ]


class TestRecord:
    def test_encode_keeps_sources_but_never_base64(self, png):
        state = DecisionState(
            text="Which animal?", attachments=[png, PNG_DATA_URL, PNG_B64]
        )
        assert state.encode() == {
            "text": "Which animal?",
            "attachments": [
                png,
                "data:image/png;base64,...",
                "data:image/png;base64,...",
            ],
        }

    def test_str_names_the_attachments(self):
        state = DecisionState(text="Hi", attachments="https://example.com/b.jpg")
        assert str(state) == "Hi [https://example.com/b.jpg]"


class TestModels:
    async def test_openai_sends_the_images(self, make_model, png):
        model, fake = make_model(cls=OpenAIDecisions, model_name="gpt-6-luna")
        resp = await model.aask(DecisionState(text="Hi", attachments=png), Triage)
        assert resp.structured["is_urgent"].probability == 0.93
        [content] = [m["content"] for m in fake.calls[0]["input"]]
        assert content[1] == {"type": "input_image", "image_url": PNG_DATA_URL}

    @pytest.mark.parametrize(
        "cls, model_name",
        [(TypeSafeAI, "jev-latest"), (OpenRouterAI, "typesafe/jev-1.13")],
    )
    async def test_system_one_vendors_reject_images_before_any_request(
        self, monkeypatch, png, cls, model_name
    ):
        # the real litellm.adecisions, with the network cut off
        async def no_network(*args, **kwargs):
            raise AssertionError("a request was sent")

        monkeypatch.setattr(httpx.AsyncClient, "send", no_network)
        model = cls(model_name, api_key="key")
        with pytest.raises(DecisionProviderRequestError, match="input_image"):
            await model.aask(DecisionState(text="Hi", attachments=png), Triage)
