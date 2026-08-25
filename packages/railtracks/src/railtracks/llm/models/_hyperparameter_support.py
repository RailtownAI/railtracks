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


def default_reasoning_effort_for_tools(
    model_name: str,
    reasoning_effort: str | None,
    *,
    has_tools: bool,
) -> str | None:
    """Returns the `reasoning_effort` that should actually be sent for a call that may
    include tools.

    OpenAI reasoning models (the gpt-5.4+ family) silently substitute their own non-"none"
    default `reasoning_effort` server-side when the caller omits it, and that default
    conflicts with function tools on `/v1/chat/completions` (#1394). If the caller hasn't
    set `reasoning_effort` explicitly, tools are present, and litellm's model-info catalog
    says the model supports `reasoning_effort="none"`, force it to avoid that failure.

    An explicitly requested `reasoning_effort` is always passed through untouched — litellm's
    own Responses-API bridge already routes gpt-5.4+ tool calls through `/v1/responses` on its
    own once `reasoning_effort` is set to anything.

    Fails open (returns `reasoning_effort` unchanged) whenever litellm can't tell us the model
    supports "none" reasoning — we never guess.
    """
    if reasoning_effort is not None or not has_tools:
        return reasoning_effort

    try:
        model_info = litellm.get_model_info(model_name)
    except Exception:
        return reasoning_effort

    if model_info.get("supports_reasoning") and model_info.get(
        "supports_none_reasoning_effort"
    ):
        return "none"

    return reasoning_effort
