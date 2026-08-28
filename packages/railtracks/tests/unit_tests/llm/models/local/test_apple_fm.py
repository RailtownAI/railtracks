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

    class _FoundationModelsError(Exception):
        pass

    class _GuardrailViolationError(_FoundationModelsError):
        pass

    class _RefusalError(_FoundationModelsError):
        pass

    class _AssetsUnavailableError(_FoundationModelsError):
        pass

    fm = MagicMock(name="apple_fm_sdk")
    fm.FoundationModelsError = _FoundationModelsError
    fm.GuardrailViolationError = _GuardrailViolationError
    fm.RefusalError = _RefusalError
    fm.AssetsUnavailableError = _AssetsUnavailableError

    class _UseCase:
        GENERAL = "GENERAL"
        CONTENT_TAGGING = "CONTENT_TAGGING"

    class _Guardrails:
        DEFAULT = "DEFAULT"
        PERMISSIVE_CONTENT_TRANSFORMATIONS = "PERMISSIVE"

    fm.SystemLanguageModelUseCase = _UseCase
    fm.SystemLanguageModelGuardrails = _Guardrails

    class _SamplingMode:
        @staticmethod
        def random(seed=None):
            return {"seed": seed}

        @staticmethod
        def greedy():
            return "greedy"

    fm.SamplingMode = _SamplingMode

    def _generation_options(**kwargs):
        return {"opts": kwargs}

    fm.GenerationOptions = _generation_options

    model_handle = MagicMock()
    model_handle.is_available.return_value = is_available
    fm.SystemLanguageModel = MagicMock(return_value=model_handle)

    session = MagicMock(name="LanguageModelSession")
    if respond_raise is not None:
        session.respond = AsyncMock(side_effect=respond_raise)
    else:
        session.respond = AsyncMock(return_value=respond_return)

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

    session.stream_response = MagicMock(
        side_effect=lambda prompt, options=None: _Stream(
            stream_snapshots or [], stream_raise
        )
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
    from railtracks.llm.models.local.apple_fm import (
        AppleFMLLM,
        AppleFMSafetyRefusalError,
        AppleFMUnavailableError,
    )

    return AppleFMLLM, AppleFMUnavailableError, AppleFMSafetyRefusalError


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
    AppleFMLLM, _, _ = _import_apple_fm_llm()

    llm = AppleFMLLM()
    assert llm.model_name() == "apple-fm-general"

    from railtracks.llm import ModelProvider

    assert llm.model_provider() == ModelProvider.APPLE_FM
    assert AppleFMLLM.model_gateway() == ModelProvider.APPLE_FM


def test_construction_raises_when_unavailable():
    _install_fake_sdk(is_available=(False, "device not supported"))
    AppleFMLLM, AppleFMUnavailableError, _ = _import_apple_fm_llm()

    with pytest.raises(AppleFMUnavailableError) as exc:
        AppleFMLLM()
    assert "device not supported" in str(exc.value)


def test_unsupported_hyperparameter_raises(fake_sdk):
    from railtracks.llm import UnsupportedHyperparameterError

    AppleFMLLM, _, _ = _import_apple_fm_llm()
    with pytest.raises(UnsupportedHyperparameterError):
        AppleFMLLM(top_p=0.9)


def test_import_error_when_sdk_missing():
    sys.modules.pop("apple_fm_sdk", None)
    with patch.dict(sys.modules, {"apple_fm_sdk": None}):
        AppleFMLLM, _, _ = _import_apple_fm_llm()
        with pytest.raises(ImportError) as exc:
            AppleFMLLM()
        assert "railtracks[apple]" in str(exc.value)


# ---------- chat -----------------------------------------------------------


def test_achat_returns_response_with_null_usage(fake_sdk):
    _, _, session = fake_sdk
    session.respond = AsyncMock(return_value="hello there")
    AppleFMLLM, _, _ = _import_apple_fm_llm()
    llm = AppleFMLLM()

    resp = asyncio.run(llm.achat(_msg_history(system="s", user="hi")))

    assert resp.text == "hello there"
    info = resp.message_info
    assert info.input_tokens is None
    assert info.output_tokens is None
    assert info.total_cost is None
    assert info.system_fingerprint is None
    assert info.model_name == "apple-fm-general"
    assert info.latency is not None and info.latency >= 0


def test_chat_sync_bridges_to_async(fake_sdk):
    _, _, session = fake_sdk
    session.respond = AsyncMock(return_value="from sync")
    AppleFMLLM, _, _ = _import_apple_fm_llm()
    llm = AppleFMLLM()
    resp = llm.chat(_msg_history(user="hi"))
    assert resp.text == "from sync"


def test_chat_sync_raises_inside_running_loop(fake_sdk):
    _, _, session = fake_sdk
    session.respond = AsyncMock(return_value="x")
    AppleFMLLM, _, _ = _import_apple_fm_llm()
    from railtracks.llm import ModelError

    llm = AppleFMLLM()

    async def run():
        with pytest.raises(ModelError) as exc:
            llm.chat(_msg_history(user="hi"))
        assert "cannot be called from inside a running event loop" in str(exc.value)

    asyncio.run(run())


def test_multi_turn_history_uses_transcript(fake_sdk):
    fm, _, session = fake_sdk
    session.respond = AsyncMock(return_value="ok")
    AppleFMLLM, _, _ = _import_apple_fm_llm()
    llm = AppleFMLLM()

    asyncio.run(
        llm.achat(_msg_history(system="s", assistant="prior", user="now"))
    )

    fm.Transcript.from_dict.assert_called_once()
    fm.LanguageModelSession.from_transcript.assert_called_once()


def test_single_turn_history_uses_plain_session(fake_sdk):
    fm, _, session = fake_sdk
    session.respond = AsyncMock(return_value="ok")
    AppleFMLLM, _, _ = _import_apple_fm_llm()
    llm = AppleFMLLM()

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
    AppleFMLLM, _, _ = _import_apple_fm_llm()
    llm = AppleFMLLM()

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
    AppleFMLLM, _, _ = _import_apple_fm_llm()
    llm = AppleFMLLM()

    asyncio.run(llm.astructured(_msg_history(user="pick"), _Answer))

    schema = captured["json_schema"]
    assert schema["additionalProperties"] is False
    assert schema["x-order"] == ["color", "reason"]
    assert "title" not in schema["properties"]["color"]


def test_astructured_bad_json_raises_llm_error(fake_sdk):
    from railtracks.exceptions.errors import LLMError

    _, _, session = fake_sdk
    session.respond = AsyncMock(return_value=_StubGeneratedContent("not-json"))
    AppleFMLLM, _, _ = _import_apple_fm_llm()
    llm = AppleFMLLM()

    with pytest.raises(LLMError):
        asyncio.run(llm.astructured(_msg_history(user="pick"), _Answer))


# ---------- streaming ------------------------------------------------------


def test_astream_chat_yields_deltas_and_final(fake_sdk):
    fake_sdk[2].stream_response = MagicMock(
        side_effect=lambda prompt, options=None: _make_stream(
            ["Hel", "Hello", "Hello world"]
        )
    )
    AppleFMLLM, _, _ = _import_apple_fm_llm()
    llm = AppleFMLLM()

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
    AppleFMLLM, _, _ = _import_apple_fm_llm()
    llm = AppleFMLLM()
    with pytest.raises(NotImplementedError) as exc:
        llm.chat_with_tools(_msg_history(user="hi"), [])
    assert "does not support tool calling" in str(exc.value)


def test_achat_with_tools_raises(fake_sdk):
    AppleFMLLM, _, _ = _import_apple_fm_llm()
    llm = AppleFMLLM()

    async def run():
        with pytest.raises(NotImplementedError):
            await llm.achat_with_tools(_msg_history(user="hi"), [])

    asyncio.run(run())


def test_astream_structured_raises(fake_sdk):
    AppleFMLLM, _, _ = _import_apple_fm_llm()
    llm = AppleFMLLM()

    async def run():
        with pytest.raises(NotImplementedError):
            async for _ in llm.astream_structured(_msg_history(user="hi"), _Answer):
                pass

    asyncio.run(run())


# ---------- error translation ---------------------------------------------


def test_guardrail_violation_becomes_safety_refusal(fake_sdk):
    fm, _, session = fake_sdk
    session.respond = AsyncMock(
        side_effect=fm.GuardrailViolationError("blocked")
    )
    AppleFMLLM, _, AppleFMSafetyRefusalError = _import_apple_fm_llm()
    llm = AppleFMLLM()

    with pytest.raises(AppleFMSafetyRefusalError):
        asyncio.run(llm.achat(_msg_history(user="hi")))


def test_assets_unavailable_becomes_unavailable(fake_sdk):
    fm, _, session = fake_sdk
    session.respond = AsyncMock(
        side_effect=fm.AssetsUnavailableError("no assets")
    )
    AppleFMLLM, AppleFMUnavailableError, _ = _import_apple_fm_llm()
    llm = AppleFMLLM()

    with pytest.raises(AppleFMUnavailableError):
        asyncio.run(llm.achat(_msg_history(user="hi")))


def test_generic_fm_error_becomes_llm_error(fake_sdk):
    from railtracks.exceptions.errors import LLMError

    fm, _, session = fake_sdk
    session.respond = AsyncMock(side_effect=fm.FoundationModelsError("boom"))
    AppleFMLLM, _, _ = _import_apple_fm_llm()
    llm = AppleFMLLM()

    with pytest.raises(LLMError):
        asyncio.run(llm.achat(_msg_history(user="hi")))
