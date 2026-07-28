"""
Per-model, per-hyperparameter support checks for the "common hyperparameters"
(temperature, top_p, max_tokens, frequency_penalty, presence_penalty, reasoning_effort,
service_tier, verbosity).

`litellm.get_supported_openai_params` is the default source of truth, but it is
known to be stale for a few specific model/hyperparameter combinations. `_MANUAL_DENYLIST`
patches those cases; re-check against a fresh litellm release before removing an
entry.
"""

import litellm

# model-name-prefix (bare, no provider prefix) -> hyperparameters litellm mis-reports as
# supported. See litellm#26444 / litellm#28113 (Opus 4.7/4.8 temperature+top_p)
# and litellm's own docs vs. reported schema for gpt-5-codex verbosity.
_MANUAL_DENYLIST: dict[str, frozenset[str]] = {
    "claude-opus-4-7": frozenset({"temperature", "top_p"}),
    "claude-opus-4-8": frozenset({"temperature", "top_p"}),
    "gpt-5-codex": frozenset({"verbosity"}),
    "gpt-5.1-codex": frozenset({"verbosity"}),
    # Gemini API rejects both penalty hyperparameters with a 400 ("Penalty is not
    # enabled for models/...") despite litellm reporting them as supported.
    # Confirmed empirically on gemini-2.5-flash; re-check before removing.
    "gemini-2.5": frozenset({"frequency_penalty", "presence_penalty"}),
}

# Provider-wide hyperparameter exclusions, for hyperparameters litellm never gates
# correctly (e.g. structural gaps, not just stale schema entries). Documented extension
# point; empty for now. Prob won't need but still.
_PROVIDER_STRUCTURAL_DENYLIST: dict[str, frozenset[str]] = {}

# provider -> sets of hyperparameters that cannot be specified together, even though
# each is individually supported. Confirmed empirically (2026-07-28) on
# claude-sonnet-4-5, claude-sonnet-4-6, and claude-opus-4-1 — treated as an
# Anthropic-wide rule rather than a per-model list since it reproduced on every model
# tested and Anthropic's rollout appears to be actively expanding.
_MUTUALLY_EXCLUSIVE: dict[str, list[frozenset[str]]] = {
    "anthropic": [frozenset({"temperature", "top_p"})],
}


def find_mutually_exclusive_conflict(
    custom_llm_provider: str, hyperparameters_set: frozenset[str]
) -> frozenset[str] | None:
    """The first mutually-exclusive hyperparameter group fully present in
    `hyperparameters_set`, if any."""
    for combo in _MUTUALLY_EXCLUSIVE.get(custom_llm_provider, []):
        if combo <= hyperparameters_set:
            return combo
    return None


def is_hyperparameter_supported(
    model_name: str, custom_llm_provider: str, hyperparameter: str
) -> bool:
    """
    Whether `hyperparameter` is safe to send to `model_name` on `custom_llm_provider`.

    Checks the manual denylists first, then falls back to
    `litellm.get_supported_openai_params`. Fails open (returns True) if litellm
    itself can't answer, so we never block usage over a litellm-side error.
    """
    bare_name = model_name.split("/")[-1]
    for prefix, denied in _MANUAL_DENYLIST.items():
        if bare_name.startswith(prefix) and hyperparameter in denied:
            return False

    if hyperparameter in _PROVIDER_STRUCTURAL_DENYLIST.get(
        custom_llm_provider, frozenset()
    ):
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

    return hyperparameter in supported
