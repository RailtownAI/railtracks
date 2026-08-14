# LLM-level guardrail internals. The authoring bases live in llm/concrete.py
# (InputGuard, OutputGuard) and llm/llm_guard.py (BaseLLMGuardrail). Neither is
# re-exported from railtracks.guardrails or railtracks.guardrails.core -- import
# them from railtracks.guardrails.llm.concrete directly, or author guards with
# the decorator API (railtracks.guardrails.input_guard / .output_guard) instead.

