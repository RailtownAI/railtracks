# Common LLM Hyperparameters

Every `rt.llm.*` model wrapper accepts a shared set of common hyperparameters for
controlling sampling, output length, and reasoning behavior.

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

`reasoning_effort` accepts one of `"minimal"`, `"low"`, `"medium"`, `"high"`:

```python
--8<-- "docs/scripts/documentation/common_hyperparams.py:reasoning_effort"
```

## Not every model supports every hyperparameter

For example, only OpenAI's GPT-5-series supports `verbosity`, and newer Anthropic
models restrict `temperature`/`top_p` in ways that vary by model. Railtracks checks
this **when you construct the model**, before making any network call, and raises
immediately if a hyperparameter (or combination of hyperparameters) isn't supported:

```python
--8<-- "docs/scripts/documentation/common_hyperparams.py:fail_fast"
```

!!! tip "Railtracks Recommendation"
    Treat `UnsupportedHyperparameterError` / `MutuallyExclusiveHyperparametersError` at
    construction as an actionable signal, not a bug to work around: it's telling you
    the provider would reject the request either way, just with a much less obvious
    error deeper into a run.

## Things to know

- **Anthropic**: Opus 4.7 and later reject non-default `temperature`/`top_p`. Separately,
  specifying `temperature` **and** `top_p` together is rejected on Anthropic models in
  general. Pass at most one of the two.
- **OpenAI**: `verbosity` is only supported on the GPT-5 series, and not on the Codex
  variants (`gpt-5-codex`, `gpt-5.1-codex`, etc.).
- **Gemini**: `frequency_penalty` and `presence_penalty` are not currently supported.

Railtracks keeps this list current as providers change their behavior. If a
hyperparameter you expect to work gets rejected, check here first.

## Invalid values

Railtracks does not validate hyperparameter *values*, only whether a hyperparameter is
supported at all for the model you're using. An out-of-range or wrong-type value (e.g.
`temperature=999`, `temperature="not a number"`) is sent through as-is and the provider
will reject it with a clear, specific error (e.g. "Expected a value <= 2, but got 999").

One exception: OpenAI currently accepts an invalid `verbosity` value without
complaint. If you're setting `verbosity`, double-check the value against OpenAI's docs
rather than relying on an error to catch a typo.
