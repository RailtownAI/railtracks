"""Unit tests for wrap_llm/before_llm/after_llm's `name` handling.

The bare decorator forms (@wrap_llm, @before_llm, @after_llm) are already exercised
elsewhere (e.g. test_guardrail_ordering.py uses a bare @before_llm), but the
parametrized form -- @wrap_llm(name=...), @before_llm(name=...), @after_llm(name=...)
-- had zero direct test coverage before this file.

The bare-form `.name` tests below are regression tests for a bug where, with no
explicit name, `.name` fell back to the decorator's internal inner-closure name
(`"wrapped"`/`"wrapper"`) instead of the original decorated function's name.
"""

from __future__ import annotations

import pytest
from railtracks.built_nodes.llm.middleware import after_llm, before_llm, wrap_llm
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import AssistantMessage, UserMessage
from railtracks.llm.response import MessageInfo, Response


def _messages() -> MessageHistory:
    return MessageHistory([UserMessage("hi")])


def _response(text: str = "hi") -> Response:
    return Response(message=AssistantMessage(content=text), message_info=MessageInfo())


@pytest.mark.asyncio
async def test_wrap_llm_parametrized_sets_name_and_still_runs():
    @wrap_llm(name="custom-wrap")
    async def middleware(call, message_history, schema, tools):
        result = await call(message_history, schema, tools)
        return Response(
            message=AssistantMessage(content=result.text + "!"),
            message_info=result.message_info,
        )

    assert middleware.name == "custom-wrap"

    async def core(message_history, schema, tools):
        return _response("hi")

    wrapped = middleware.wrap(core)
    result = await wrapped(_messages(), None, None)
    assert result.text == "hi!"


@pytest.mark.asyncio
async def test_before_llm_parametrized_sets_name_and_transforms_request():
    @before_llm(name="custom-before")
    async def middleware(message_history, schema, tools):
        new_history = MessageHistory([*message_history, UserMessage("appended")])
        return new_history, schema, tools

    assert middleware.name == "custom-before"

    seen = {}

    async def core(message_history, schema, tools):
        seen["history"] = message_history
        return _response()

    wrapped = middleware.wrap(core)
    await wrapped(_messages(), None, None)

    assert [m.content for m in seen["history"]] == ["hi", "appended"]


@pytest.mark.asyncio
async def test_after_llm_parametrized_sets_name_and_transforms_response():
    @after_llm(name="custom-after")
    async def middleware(response):
        return Response(
            message=AssistantMessage(content=response.text.upper()),
            message_info=response.message_info,
        )

    assert middleware.name == "custom-after"

    async def core(message_history, schema, tools):
        return _response("hi")

    wrapped = middleware.wrap(core)
    result = await wrapped(_messages(), None, None)
    assert result.text == "HI"


# ---------------------------------------------------------------------------
# Bare-decorator naming (no explicit name=) -- must default to the original
# decorated function's name, not the decorator's internal inner-closure name.
# ---------------------------------------------------------------------------


def test_wrap_llm_bare_defaults_name_to_original_function():
    @wrap_llm
    async def my_wrap_middleware(call, message_history, schema, tools):
        return await call(message_history, schema, tools)

    assert my_wrap_middleware.name == "my_wrap_middleware"


def test_before_llm_bare_defaults_name_to_original_function():
    @before_llm
    async def my_before_middleware(message_history, schema, tools):
        return message_history, schema, tools

    assert my_before_middleware.name == "my_before_middleware"


def test_after_llm_bare_defaults_name_to_original_function():
    @after_llm
    async def my_after_middleware(response):
        return response

    assert my_after_middleware.name == "my_after_middleware"
