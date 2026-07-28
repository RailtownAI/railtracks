# Common LLM Hyperparameters

Every `rt.llm.*` model wrapper accepts a shared set of "common hyperparameters" for
controlling sampling, output length, and reasoning behavior — passed straight through
to the underlying provider via litellm.

| Hyperparameter | Controls |
|---|---|
| `temperature` | Randomness/diversity of the response. |
| `top_p` | Nucleus sampling: cumulative-probability cutoff for candidate tokens. |
| `max_tokens` | Maximum tokens to generate. |
| `frequency_penalty` | Penalizes tokens by how often they've already appeared. |
| `presence_penalty` | Penalizes tokens that have already appeared at all. |
| `reasoning_effort` | Requested reasoning effort, for reasoning-capable models. |
| `service_tier` | Requested service tier (provider-specific). |
| `verbosity` | Requested output verbosity (currently OpenAI GPT-5-series only). |

```python
--8<-- "docs/scripts/documentation/common_hyperparams.py:basic_usage"
```

`reasoning_effort` also accepts the portable `rt.llm.ReasoningEffort` enum instead of a
raw string:

```python
--8<-- "docs/scripts/documentation/common_hyperparams.py:reasoning_effort"
```

## Per-model support gating

Not every model supports every hyperparameter — for example Anthropic's Opus 4.7+
rejects non-default `temperature`/`top_p`, and only OpenAI's GPT-5-series supports
`verbosity`. Railtracks checks this **at construction time**, using litellm's
`get_supported_openai_params` as the source of truth, and raises immediately instead of
silently dropping the hyperparameter:

```python
--8<-- "docs/scripts/documentation/common_hyperparams.py:fail_fast"
```

This also catches hyperparameter *combinations* that are individually valid but can't
be used together — currently, Anthropic rejects `temperature` and `top_p` specified at
the same time, on every model tested, even though each works fine alone.

!!! tip "Railtracks Recommendation"
    Treat `UnsupportedHyperparameterError` / `MutuallyExclusiveHyperparametersError` at
    construction as an actionable signal, not a bug to work around — it's telling you
    the provider will reject the request server-side either way, just with a much less
    obvious error deeper in a run.

## Known provider gotchas

litellm's schema is the default source of truth for per-model support, but it's known
to be stale for a few specific cases. These are patched with a manual denylist in
[`llm/models/_hyperparameter_support.py`](https://github.com/RailtownAI/railtracks/blob/main/packages/railtracks/src/railtracks/llm/models/_hyperparameter_support.py)
— check there for the current, up-to-date list:

- **Anthropic Opus 4.7/4.8** reject `temperature`/`top_p` with a 400, despite litellm
  reporting both as supported ([litellm#26444](https://github.com/BerriAI/litellm/issues/26444),
  fix pending in [litellm#28113](https://github.com/BerriAI/litellm/pull/28113)).
- **Anthropic `temperature` + `top_p` together** are rejected on every Anthropic model
  tested (not just Opus 4.7+) — this is a combination rule, not a single-hyperparameter
  one, and raises `MutuallyExclusiveHyperparametersError` rather than
  `UnsupportedHyperparameterError`.
- **`gpt-5-codex`/`gpt-5.1-codex`** don't support `verbosity`, despite litellm's schema
  listing it.
- **Gemini (`gemini-2.5-*`)** rejects `frequency_penalty`/`presence_penalty` with a 400
  ("Penalty is not enabled for models/..."), despite litellm reporting them as supported.

This list can grow as providers change behavior faster than litellm's schema catches up
— if you hit a similar mismatch, it likely belongs in the same denylist.

## Invalid values

Railtracks does not validate hyperparameter *values* — only whether a hyperparameter is
supported at all for the resolved model. An out-of-range or wrong-type value (e.g.
`temperature=999`, `temperature="bullshit"`) is passed through as-is and surfaces as a
provider-native error, which is typically clear and specific (e.g. `"Expected a value
<= 2, but got 999"`).

The one confirmed exception: `verbosity` on OpenAI (checked on `gpt-5-mini`) is
**silently accepted even when invalid**, with no error at all. If you're setting
`verbosity`, double-check the value against the provider's docs rather than relying on
an error to catch a typo.
