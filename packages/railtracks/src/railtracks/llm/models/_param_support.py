"""
Per-model, per-param support checks for the "common params" (temperature, top_p,
max_tokens, frequency_penalty, presence_penalty, reasoning_effort, service_tier,
verbosity).

`litellm.get_supported_openai_params` is the default source of truth, but it is
known to be stale for a few specific model/param combinations. `_MANUAL_DENYLIST`
patches those cases; re-check against a fresh litellm release before removing an
entry.
"""

import litellm

# model-name-prefix (bare, no provider prefix) -> params litellm mis-reports as
# supported. See litellm#26444 / litellm#28113 (Opus 4.7/4.8 temperature+top_p)
# and litellm's own docs vs. reported schema for gpt-5-codex verbosity.
_MANUAL_DENYLIST: dict[str, frozenset[str]] = {
    "claude-opus-4-7": frozenset({"temperature", "top_p"}),
    "claude-opus-4-8": frozenset({"temperature", "top_p"}),
    "gpt-5-codex": frozenset({"verbosity"}),
    "gpt-5.1-codex": frozenset({"verbosity"}),
}

# Provider-wide param exclusions, for params litellm never gates correctly
# (e.g. structural gaps, not just stale schema entries). Documented extension
# point; empty for now. Prob won't need but still.
_PROVIDER_STRUCTURAL_DENYLIST: dict[str, frozenset[str]] = {}


def is_param_supported(model_name: str, custom_llm_provider: str, param: str) -> bool:
    """
    Whether `param` is safe to send to `model_name` on `custom_llm_provider`.

    Checks the manual denylists first, then falls back to
    `litellm.get_supported_openai_params`. Fails open (returns True) if litellm
    itself can't answer, so we never block usage over a litellm-side error.
    """
    bare_name = model_name.split("/")[-1]
    for prefix, denied in _MANUAL_DENYLIST.items():
        if bare_name.startswith(prefix) and param in denied:
            return False

    if param in _PROVIDER_STRUCTURAL_DENYLIST.get(custom_llm_provider, frozenset()):
        return False

    try:
        supported = litellm.get_supported_openai_params(
            model=model_name, custom_llm_provider=custom_llm_provider
        )
    except Exception:
        return True

    if supported is None:
        # litellm couldn't answer for this model/provider combo (e.g. an
        # unrecognized provider) — fail open rather than block usage.
        return True

    return param in supported
