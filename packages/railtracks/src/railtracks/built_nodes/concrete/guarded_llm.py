"""
Guarded LLM types: LLM nodes with input/output guardrails via LLMGuardrailsMixin.

Uses the higher-level design: hooks (_pre_invoke / _post_invoke) on LLMBase, implemented
by the mixin. No separate invoke() logic; each base type's invoke() calls the hooks.

Set guardrails= when building the node (e.g. via agent_node(..., guardrails=Guard(...))).

Streaming note: streaming is decided at the call site (`rt.astream`) rather than by the node
class, so there are no separate streaming variants. When a guarded node streams, the raw
chunks are broadcast as they arrive and the output guardrails run on the complete buffered
response — the final returned response is gated, but chunks already emitted are not recalled.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

from railtracks.guardrails.llm.mixin import LLMGuardrailsMixin

from .structured_llm_base import StructuredLLM
from .structured_tool_call_llm_base import StructuredToolCallLLM
from .terminal_llm_base import TerminalLLM
from .tool_call_llm_base import ToolCallLLM

_TBaseModel = TypeVar("_TBaseModel", bound=BaseModel)


class GuardedTerminalLLM(LLMGuardrailsMixin, TerminalLLM):
    pass


class GuardedStructuredLLM(
    LLMGuardrailsMixin, StructuredLLM[_TBaseModel], Generic[_TBaseModel]
):
    pass


class GuardedToolCallLLM(LLMGuardrailsMixin, ToolCallLLM):
    pass


class GuardedStructuredToolCallLLM(
    LLMGuardrailsMixin, StructuredToolCallLLM[_TBaseModel], Generic[_TBaseModel]
):
    pass
