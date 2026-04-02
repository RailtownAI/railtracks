"""
Guarded LLM types: LLM nodes with input/output guardrails via LLMGuardrailsMixin.

Uses the higher-level design: hooks (_pre_invoke / _post_invoke) on LLMBase, implemented
by the mixin. No separate invoke() logic; each base type's invoke() calls the hooks.

Set guardrails= when building the node (e.g. via agent_node(..., guardrails=Guard(...))).
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

from railtracks.guardrails.llm.mixin import LLMGuardrailsMixin

from .structured_llm_base import StreamingStructuredLLM, StructuredLLM
from .terminal_llm_base import StreamingTerminalLLM, TerminalLLM

_TBaseModel = TypeVar("_TBaseModel", bound=BaseModel)


class GuardedTerminalLLM(LLMGuardrailsMixin, TerminalLLM):
    pass


class GuardedStreamingTerminalLLM(LLMGuardrailsMixin, StreamingTerminalLLM):
    pass


class GuardedStructuredLLM(
    LLMGuardrailsMixin, StructuredLLM[_TBaseModel], Generic[_TBaseModel]
):
    pass


class GuardedStreamingStructuredLLM(
    LLMGuardrailsMixin, StreamingStructuredLLM[_TBaseModel], Generic[_TBaseModel]
):
    pass
