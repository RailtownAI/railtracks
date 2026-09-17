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

## Accessing the reasoning a model returned

Reasoning-capable providers (Anthropic, DeepSeek, Gemini, OpenAI in part) can return
their intermediate "thinking" alongside the answer. When they do, railtracks surfaces it
on the response so you never have to reach into provider internals:

```python
response = await model.achat(history)

print(response.reasoning)              # human-readable reasoning text, or None
print(response.message.reasoning_content)  # same text, on the message
print(response.message.thinking_blocks)    # structured, signed blocks (or None)
```

- `response.reasoning` (and `response.message.reasoning_content`) is the plain-text
  reasoning: `None` when the model returned none (a non-reasoning model, or one not
  asked to expose its thinking).
- `response.message.thinking_blocks` holds the structured blocks, including any provider
  signatures. Because reasoning lives on the assistant *message*, it travels with the
  message in history and is included when the run graph is serialized.

Streaming works the same way: the reasoning is accumulated and attached to the final
`Response` yielded by `astream_*` (reasoning is not emitted as separate stream chunks).

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
