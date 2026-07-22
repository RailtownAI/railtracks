# Contributing a Guardrail

A guardrail is a middleware specialized for LLM input/output. If you have built a reusable rail; a new PII entity, a domain-specific content filter, or a policy check, contributing it as a prebuilt guard makes it importable from `rt.prebuilt.guardrails`.

To author a rail, subclass `InputGuard` or `OutputGuard` and implement `__call__(self, event) -> GuardrailDecision`; see [Custom Guards](overview.md#custom-guards) for the pattern (and the decorator API for quick, local guards). To make it a shipped guardrail:

1. Implement the guard under `packages/railtracks/src/railtracks/prebuilt/guardrails/` (input/output modules; shared logic in a private subpackage such as `_pii/`).
2. Re-export the public name from `prebuilt/guardrails/__init__.py`.
3. Add unit tests under `packages/railtracks/tests/unit_tests/guardrails/`, using `decide()` for isolated assertions.
4. Add a dedicated page under `docs/.../middleware/prebuilt/list/` with a runnable snippet in `docs/scripts/`.

Keep dependencies optional or zero unless the feature truly needs them, and document behavior, limits, and false-positive/false-negative tradeoffs briefly.

We would love your contribution. See also the general [prebuilt middleware contribution guide](../prebuilt/contributions.md).
