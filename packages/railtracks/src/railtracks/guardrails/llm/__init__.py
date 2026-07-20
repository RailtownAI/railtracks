# LLM-level guardrail internals. The authoring bases live in llm/concrete.py
# (InputGuard, OutputGuard) and llm/llm_guard.py (BaseLLMGuardrail); they are
# re-exported from railtracks.guardrails / railtracks.guardrails.core. Concrete
# prebuilt guards moved to railtracks.prebuilt.guardrails (design-docs/addon-interface, D6).
#
# Intentionally does NOT import concrete here: core/__init__ re-exports InputGuard/
# OutputGuard from llm.concrete, so importing concrete here too creates an
# order-dependent cycle. Keeping this empty makes package init order irrelevant.

__all__: list[str] = []
