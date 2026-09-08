"""Unit tests for AppleFMLLM.

These tests mock `apple_fm_sdk` so they run on any platform, not just macOS
26+ Apple Silicon. Live-device coverage lives in `tests/llm_live_tests/`.
"""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

# ---------- fixtures ------------------------------------------------------


class _StubGeneratedContent:
    def __init__(self, payload: str):
        self._payload = payload

    def to_json(self) -> str:
        return self._payload


class _FoundationModelsError(Exception):
    pass


class _GuardrailViolationError(_FoundationModelsError):
    pass


class _RefusalError(_FoundationModelsError):
    pass


class _AssetsUnavailableError(_FoundationModelsError):
    pass


class _UseCase:
    GENERAL = "GENERAL"
    CONTENT_TAGGING = "CONTENT_TAGGING"


class _Guardrails:
    DEFAULT = "DEFAULT"
    PERMISSIVE_CONTENT_TRANSFORMATIONS = "PERMISSIVE"


class _SamplingMode:
    @staticmethod
    def random(seed=None):
        return {"seed": seed}

    @staticmethod
    def greedy():
        return "greedy"


class _Stream:
    def __init__(self, snapshots, raise_on):
        self._snapshots = snapshots
        self._raise = raise_on
        self._i = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._raise is not None and self._i == 0:
            raise self._raise
        if self._i >= len(self._snapshots):
            raise StopAsyncIteration
        v = self._snapshots[self._i]
        self._i += 1
        return v


def _make_fake_fm_module() -> MagicMock:
    fm = MagicMock(name="apple_fm_sdk")
    fm.FoundationModelsError = _FoundationModelsError
    fm.GuardrailViolationError = _GuardrailViolationError
    fm.RefusalError = _RefusalError
    fm.AssetsUnavailableError = _AssetsUnavailableError
    fm.SystemLanguageModelUseCase = _UseCase
    fm.SystemLanguageModelGuardrails = _Guardrails
    fm.SamplingMode = _SamplingMode
    fm.GenerationOptions = lambda **kwargs: {"opts": kwargs}
    return fm


def _make_fake_session(
    *, respond_return, respond_raise, stream_snapshots, stream_raise
):
    session = MagicMock(name="LanguageModelSession")
    if respond_raise is not None:
        session.respond = AsyncMock(side_effect=respond_raise)
    else:
        session.respond = AsyncMock(return_value=respond_return)
    session.stream_response = MagicMock(
        side_effect=lambda prompt, options=None: _Stream(
            stream_snapshots or [], stream_raise
        )
    )
    return session


def _install_fake_sdk(
    *,
    is_available=(True, None),
    respond_return=None,
    respond_raise=None,
    stream_snapshots=None,
    stream_raise=None,
    transcript_available=True,
):
    """Insert a MagicMock `apple_fm_sdk` into sys.modules with the surface
    the provider touches.
    """
    fm = _make_fake_fm_module()

    model_handle = MagicMock()
    model_handle.is_available.return_value = is_available
    fm.SystemLanguageModel = MagicMock(return_value=model_handle)

    session = _make_fake_session(
        respond_return=respond_return,
        respond_raise=respond_raise,
        stream_snapshots=stream_snapshots,
        stream_raise=stream_raise,
    )
    fm.LanguageModelSession = MagicMock(return_value=session)
    fm.LanguageModelSession.from_transcript = MagicMock(return_value=session)

    if transcript_available:
        fm.Transcript = MagicMock()
        fm.Transcript.from_dict = MagicMock(return_value="transcript")
    else:
        del fm.Transcript

    sys.modules["apple_fm_sdk"] = fm
    return fm, model_handle, session


@pytest.fixture
def fake_sdk():
    """Insert a fake apple_fm_sdk; wipe cached railtracks modules that import
    it lazily so they see the fake."""
    prior = sys.modules.get("apple_fm_sdk")
    fm, model_handle, session = _install_fake_sdk(respond_return="hi")
    yield fm, model_handle, session
    if prior is not None:
        sys.modules["apple_fm_sdk"] = prior
    else:
        sys.modules.pop("apple_fm_sdk", None)


# ---------- helpers --------------------------------------------------------


def _import_apple_fm_llm():
    """Return the freshly-imported apple_fm module so tests access
    `mod.AppleFMLLM`, `mod.AppleFMUnavailableError`, etc. without local
    rebinding (avoids N806 on class names).
    """
    from railtracks.llm.models.local import apple_fm

    return apple_fm


def _msg_history(*, user="hi", system=None, assistant=None):
    from railtracks.llm import (
        AssistantMessage,
        MessageHistory,
        SystemMessage,
        UserMessage,
    )

    items = []
    if system is not None:
        items.append(SystemMessage(system))
    if assistant is not None:
        items.append(UserMessage("earlier"))
        items.append(AssistantMessage(assistant))
    items.append(UserMessage(user))
    return MessageHistory(items)


# ---------- construction ---------------------------------------------------


def test_construction_stores_metadata(fake_sdk):
    mod = _import_apple_fm_llm()

    llm = mod.AppleFMLLM()
    assert llm.model_name() == "apple-fm"

    from railtracks.llm import ModelProvider

    assert llm.model_provider() == ModelProvider.APPLE_FM
    assert mod.AppleFMLLM.model_gateway() == ModelProvider.APPLE_FM


def test_construction_raises_when_unavailable():
    _install_fake_sdk(is_available=(False, "device not supported"))
    mod = _import_apple_fm_llm()

    with pytest.raises(mod.AppleFMUnavailableError) as exc:
        mod.AppleFMLLM()
    assert "device not supported" in str(exc.value)


def test_unsupported_hyperparameter_raises(fake_sdk):
    from railtracks.llm import UnsupportedHyperparameterError

    mod = _import_apple_fm_llm()
    with pytest.raises(UnsupportedHyperparameterError):
        mod.AppleFMLLM(top_p=0.9)


def test_import_error_when_sdk_missing():
    sys.modules.pop("apple_fm_sdk", None)
    with patch.dict(sys.modules, {"apple_fm_sdk": None}):
        mod = _import_apple_fm_llm()
        with pytest.raises(ImportError) as exc:
            mod.AppleFMLLM()
        assert "railtracks[apple]" in str(exc.value)


# ---------- chat -----------------------------------------------------------


def test_achat_returns_response_with_null_usage(fake_sdk):
    _, _, session = fake_sdk
    session.respond = AsyncMock(return_value="hello there")
    mod = _import_apple_fm_llm()
    llm = mod.AppleFMLLM()

    resp = asyncio.run(llm.achat(_msg_history(system="s", user="hi")))

    assert resp.text == "hello there"
    info = resp.message_info
    assert info.input_tokens is None
    assert info.output_tokens is None
    assert info.total_cost is None
    assert info.system_fingerprint is None
    assert info.model_name == "apple-fm"
    assert info.latency is not None and info.latency >= 0


def test_chat_sync_bridges_to_async(fake_sdk):
    _, _, session = fake_sdk
    session.respond = AsyncMock(return_value="from sync")
    mod = _import_apple_fm_llm()
    llm = mod.AppleFMLLM()
    resp = llm.chat(_msg_history(user="hi"))
    assert resp.text == "from sync"


def test_chat_sync_raises_inside_running_loop(fake_sdk):
    _, _, session = fake_sdk
    session.respond = AsyncMock(return_value="x")
    mod = _import_apple_fm_llm()
    from railtracks.llm import ModelError

    llm = mod.AppleFMLLM()

    async def run():
        with pytest.raises(ModelError) as exc:
            llm.chat(_msg_history(user="hi"))
        assert "cannot be called from inside a running event loop" in str(exc.value)

    asyncio.run(run())


def test_multi_turn_history_uses_transcript(fake_sdk):
    fm, _, session = fake_sdk
    session.respond = AsyncMock(return_value="ok")
    mod = _import_apple_fm_llm()
    llm = mod.AppleFMLLM()

    asyncio.run(llm.achat(_msg_history(system="s", assistant="prior", user="now")))

    fm.Transcript.from_dict.assert_called_once()
    fm.LanguageModelSession.from_transcript.assert_called_once()


def test_single_turn_history_uses_plain_session(fake_sdk):
    fm, _, session = fake_sdk
    session.respond = AsyncMock(return_value="ok")
    mod = _import_apple_fm_llm()
    llm = mod.AppleFMLLM()

    asyncio.run(llm.achat(_msg_history(system="s", user="hi")))

    fm.LanguageModelSession.from_transcript.assert_not_called()
    fm.LanguageModelSession.assert_called()


# ---------- structured -----------------------------------------------------


class _Answer(BaseModel):
    color: str
    reason: str


def test_astructured_returns_parsed_model(fake_sdk):
    _, _, session = fake_sdk
    session.respond = AsyncMock(
        return_value=_StubGeneratedContent('{"color":"red","reason":"warm"}')
    )
    mod = _import_apple_fm_llm()
    llm = mod.AppleFMLLM()

    resp = asyncio.run(llm.astructured(_msg_history(user="pick"), _Answer))

    assert isinstance(resp.message.content, _Answer)
    assert resp.message.content.color == "red"


def test_astructured_normalizes_schema(fake_sdk):
    _, _, session = fake_sdk
    captured: dict = {}

    async def _capture(prompt, **kwargs):
        captured.update(kwargs)
        return _StubGeneratedContent('{"color":"red","reason":"warm"}')

    session.respond = _capture
    mod = _import_apple_fm_llm()
    llm = mod.AppleFMLLM()

    asyncio.run(llm.astructured(_msg_history(user="pick"), _Answer))

    schema = captured["json_schema"]
    assert schema["additionalProperties"] is False
    assert schema["x-order"] == ["color", "reason"]
    assert "title" not in schema["properties"]["color"]


def test_astructured_bad_json_raises_model_error(fake_sdk):
    from railtracks.llm import ModelError

    _, _, session = fake_sdk
    session.respond = AsyncMock(return_value=_StubGeneratedContent("not-json"))
    mod = _import_apple_fm_llm()
    llm = mod.AppleFMLLM()

    with pytest.raises(ModelError):
        asyncio.run(llm.astructured(_msg_history(user="pick"), _Answer))


# ---- normalizer coverage for realistic pydantic shapes -------------------


def test_normalizer_handles_nested_ref_enum_and_list():
    """Nested BaseModels ($ref/$defs), Literal→enum, Optional, list[Model],
    and Field descriptions should all round-trip cleanly through the
    normalizer — this mirrors the shape used in
    v2_test_agent/apple-fm/structured.py (Event/Attendee).
    """
    from typing import Literal, Optional

    from pydantic import BaseModel, Field
    from railtracks.llm.models.local.apple_fm import (
        _normalize_schema_for_apple,
    )

    class Attendee(BaseModel):
        first_name: str = Field(description="First name.")
        last_name: Optional[str] = Field(None, description="Last name if stated.")

    class Event(BaseModel):
        name: str = Field(description="Short name.")
        priority: Literal["low", "medium", "high"] = Field(description="Priority.")
        capacity: int = Field(description="Room capacity.", ge=0, le=500)
        location: Optional[str] = Field(None, description="Venue.")
        attendees: list[Attendee] = Field(
            default_factory=list, description="Named people."
        )

    schema = _normalize_schema_for_apple(Event.model_json_schema())

    # Top-level object gets Apple's required extras.
    assert schema["additionalProperties"] is False
    assert schema["x-order"] == [
        "name",
        "priority",
        "capacity",
        "location",
        "attendees",
    ]

    # $defs recursion — nested Attendee also gets additionalProperties + x-order.
    nested = schema["$defs"]["Attendee"]
    assert nested["additionalProperties"] is False
    assert nested["x-order"] == ["first_name", "last_name"]

    # Primitives lose their pydantic-generated title but keep description,
    # enum, and numeric constraints.
    props = schema["properties"]
    assert "title" not in props["name"]
    assert props["name"]["description"] == "Short name."
    assert props["priority"]["enum"] == ["low", "medium", "high"]
    assert "title" not in props["priority"]
    assert props["capacity"]["minimum"] == 0
    assert props["capacity"]["maximum"] == 500
    assert "title" not in props["capacity"]

    # Nested primitives inside $defs get the same treatment.
    nested_props = nested["properties"]
    assert "title" not in nested_props["first_name"]
    assert nested_props["first_name"]["description"] == "First name."

    # $ref links to the nested model stay intact — the walker must not touch
    # the reference itself.
    assert schema["properties"]["attendees"]["items"] == {"$ref": "#/$defs/Attendee"}


def test_attachment_raises_not_implemented(fake_sdk):
    """A UserMessage with an attachment must fail loudly rather than
    silently dropping the image and letting the model hallucinate a
    description of something it never saw.
    """
    from railtracks.llm import MessageHistory, UserMessage

    mod = _import_apple_fm_llm()
    llm = mod.AppleFMLLM()

    # A stubbed attachment on the message — real Attachment construction
    # requires a valid file path, so hand the UserMessage an object with
    # the same duck-typed shape.
    msg = UserMessage(content="what is this?")
    msg.attachment = [object()]
    history = MessageHistory([msg])

    async def run():
        with pytest.raises(NotImplementedError) as exc:
            await llm.achat(history)
        assert "attachment" in str(exc.value).lower()
        assert "hallucinate" in str(exc.value).lower()

    asyncio.run(run())


def test_normalizer_is_idempotent():
    """Running the normalizer twice should be a no-op on the second pass —
    guards against duplicate x-order entries or clobbered additionalProperties.
    """
    from pydantic import BaseModel, Field
    from railtracks.llm.models.local.apple_fm import (
        _normalize_schema_for_apple,
    )

    class M(BaseModel):
        a: str = Field(description="a")
        b: int = Field(description="b")

    once = _normalize_schema_for_apple(M.model_json_schema())
    twice = _normalize_schema_for_apple(
        _normalize_schema_for_apple(M.model_json_schema())
    )
    assert once == twice


# ---------- streaming ------------------------------------------------------


def test_astream_chat_yields_deltas_and_final(fake_sdk):
    fake_sdk[2].stream_response = MagicMock(
        side_effect=lambda prompt, options=None: _make_stream(
            ["Hel", "Hello", "Hello world"]
        )
    )
    mod = _import_apple_fm_llm()
    llm = mod.AppleFMLLM()

    async def collect():
        deltas = []
        final = None
        async for item in llm.astream_chat(_msg_history(user="stream")):
            if isinstance(item, str):
                deltas.append(item)
            else:
                final = item
        return deltas, final

    deltas, final = asyncio.run(collect())
    assert deltas == ["Hel", "lo", " world"]
    assert final is not None
    assert final.text == "Hello world"


def _make_stream(snapshots):
    class _Stream:
        def __init__(self):
            self._i = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._i >= len(snapshots):
                raise StopAsyncIteration
            v = snapshots[self._i]
            self._i += 1
            return v

    return _Stream()


# ---------- tools raise ----------------------------------------------------


def test_chat_with_tools_raises(fake_sdk):
    mod = _import_apple_fm_llm()
    llm = mod.AppleFMLLM()
    with pytest.raises(NotImplementedError) as exc:
        llm.chat_with_tools(_msg_history(user="hi"), [])
    assert "does not support tool calling" in str(exc.value)


def test_achat_with_tools_raises(fake_sdk):
    mod = _import_apple_fm_llm()
    llm = mod.AppleFMLLM()

    async def run():
        with pytest.raises(NotImplementedError):
            await llm.achat_with_tools(_msg_history(user="hi"), [])

    asyncio.run(run())


def test_astream_structured_raises(fake_sdk):
    mod = _import_apple_fm_llm()
    llm = mod.AppleFMLLM()

    async def run():
        with pytest.raises(NotImplementedError):
            async for _ in llm.astream_structured(_msg_history(user="hi"), _Answer):
                pass

    asyncio.run(run())


# ---------- error translation ---------------------------------------------


def test_guardrail_violation_becomes_safety_refusal(fake_sdk):
    fm, _, session = fake_sdk
    session.respond = AsyncMock(side_effect=fm.GuardrailViolationError("blocked"))
    mod = _import_apple_fm_llm()
    llm = mod.AppleFMLLM()

    with pytest.raises(mod.AppleFMSafetyRefusalError):
        asyncio.run(llm.achat(_msg_history(user="hi")))


def test_assets_unavailable_becomes_unavailable(fake_sdk):
    fm, _, session = fake_sdk
    session.respond = AsyncMock(side_effect=fm.AssetsUnavailableError("no assets"))
    mod = _import_apple_fm_llm()
    llm = mod.AppleFMLLM()

    with pytest.raises(mod.AppleFMUnavailableError):
        asyncio.run(llm.achat(_msg_history(user="hi")))


def test_generic_fm_error_becomes_model_error(fake_sdk):
    from railtracks.llm import ModelError

    fm, _, session = fake_sdk
    session.respond = AsyncMock(side_effect=fm.FoundationModelsError("boom"))
    mod = _import_apple_fm_llm()
    llm = mod.AppleFMLLM()

    with pytest.raises(ModelError):
        asyncio.run(llm.achat(_msg_history(user="hi")))
