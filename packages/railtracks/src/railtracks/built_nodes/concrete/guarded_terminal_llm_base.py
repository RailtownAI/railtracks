"""
Guarded terminal LLM: TerminalLLM with input/output guardrails via LLMGuardrailsMixin.

Uses the higher-level design: hooks (_pre_invoke / _post_invoke) on LLMBase, implemented
by the mixin. No separate invoke() logic; TerminalLLM.invoke() calls the hooks.
"""

from __future__ import annotations

from railtracks.guardrails.llm.mixin import LLMGuardrailsMixin

from .terminal_llm_base import TerminalLLM


class GuardedTerminalLLM(LLMGuardrailsMixin, TerminalLLM):
    """
    Terminal LLM that runs input (and optionally output) guardrails via the mixin.

    Set guardrails= when building the node (e.g. via agent_node(..., guardrails=Guard(...))).
    """

    pass
