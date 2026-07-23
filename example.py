import litellm

# Experiments for issue #1276 (common LLM param support: temperature, top_p, top_k,
# reasoning_effort, service_tier, verbosity) and the Anthropic Opus 4.7+ deprecation
# of sampling params (temperature/top_p/top_k -> 400 error), cross-checked against
# litellm's get_supported_openai_params as our proposed "source of truth" gate.

MATH_PARAMS = ["temperature", "top_p", "top_k", "frequency_penalty", "presence_penalty"]
REASONING_PARAMS = ["reasoning_effort", "thinking", "verbosity"]

MODELS = [
    # (label, model, custom_llm_provider)
    ("gpt-4o (classic sampling model)", "gpt-4o", "openai"),
    ("gpt-5 (reasoning model)", "gpt-5", "openai"),
    ("gpt-5-mini (reasoning model, has verbosity)", "gpt-5-mini", "openai"),
    ("gpt-5-codex (reasoning model, NO verbosity)", "gpt-5-codex", "openai"),
    ("o3 (reasoning model)", "o3", "openai"),
    ("claude-opus-4-1 (pre-deprecation Opus)", "claude-opus-4-1", "anthropic"),
    ("claude-opus-4-7 (sampling params deprecated by Anthropic)", "claude-opus-4-7", "anthropic"),
    ("claude-opus-4-8 (sampling params deprecated by Anthropic)", "claude-opus-4-8", "anthropic"),
    ("claude-sonnet-5 (current default sonnet)", "claude-sonnet-5", "anthropic"),
]


def supported_params(model, provider):
    try:
        return litellm.get_supported_openai_params(model=model, custom_llm_provider=provider) or []
    except Exception as e:
        return [f"ERROR: {e}"]


def classify(params):
    math = [p for p in MATH_PARAMS if p in params]
    reasoning = [p for p in REASONING_PARAMS if p in params]
    return math, reasoning


if __name__ == "__main__":
    for label, model, provider in MODELS:
        params = supported_params(model, provider)
        math, reasoning = classify(params)
        print(f"=== {label} ===")
        print(f"  model={model} provider={provider}")
        print(f"  math/sampling params reported supported: {math}")
        print(f"  reasoning/output-style params reported supported: {reasoning}")
        print()

    print("--- Known gap check: Anthropic Opus 4.7/4.8 ---")
    print("Anthropic's API rejects non-default temperature/top_p/top_k on Opus 4.7+")
    print("with a 400 error (see litellm#26444). If 'temperature'/'top_p' show up as")
    print("'supported' above for claude-opus-4-7/4-8, litellm's gate is stale and we")
    print("cannot rely on get_supported_openai_params alone for these models yet.")