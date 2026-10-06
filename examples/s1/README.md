# System One (S1) decision examples

System One models read a piece of text and answer typed questions about it with calibrated probabilities instead of prose: a yes/no (`Noul`), a pick from named labels (`Choice`), or a level on a rubric (`Score`). One request answers every question in a single forward pass. In railtracks the models live in `rt.decisions`, the way chat models live in `rt.llm`, and `rt.decision_node` turns a model plus a schema into a node, the way `rt.agent_node` does for an LLM.

- `s1_demo.py` -> start here. Triages a support inbox with Jev: one ticket through a Flow, a whole inbox routed on the probabilities (confident tickets go to a team queue, unclear ones to a person), the decision as an agent's tool, and a direct `aask` call with a JSON state.
- `jev_example.py`, `openrouter_example.py`, `upstage_example.py`, `laya_example.py`, `litellm_proxy_example.py` -> the same triage schema on each host, one file per host.

## Hosts

Every host speaks TypeSafe's `/v1/systemone` format, so they all take the same `TypeSafeSchema`; switching hosts is a one-line change.

| Class | Serves | Key | Notes |
|---|---|---|---|
| `TypeSafeAI` | TypeSafe's Jev (`jev-latest`) | `TYPESAFE_API_KEY` (required) | `TYPESAFE_API_BASE` overrides the URL |
| `OpenRouterAI` | Any S1 model on OpenRouter (`typesafe/jev-1.13`, `upstage/solar-decide`) | `OPENROUTER_API_KEY` (required) | Reports the billed cost, which becomes `result.cost` |
| `UpstageAI` | Upstage's Solar Decide (`solar-decide`) | `UPSTAGE_API_KEY` (required) | At most 26 options per Choice; no price in LiteLLM's list yet, so `cost` is `None` |
| `LayaAI` | A self-hosted Laya server (`english`, `multilingual`, `typed-decisions`) | `LAYA_API_KEY` (optional) | `LAYA_API_BASE` or `api_base=` is required; limits of 100 options, 64 questions, 50,000 characters |
| `LiteLLMProxyAI` | TypeSafe, Laya or Bespoke Nimble behind a LiteLLM proxy (`upstream=`) | `LITELLM_PROXY_API_KEY` (a virtual key) | `LITELLM_PROXY_API_BASE` is required |
| `TypeSafeCompatibleAI` | Any other compatible server, e.g. self-hosted Kev | `api_key=` (optional) | `api_base=` is required |

A request over a host's limit fails before it is sent.

## Running them

```bash
uv run python examples/s1/s1_demo.py
uv run python examples/s1/openrouter_example.py
```

Each example needs its host's key in your `.env` (see the table); `s1_demo.py` also needs `OPENAI_API_KEY` for the agent. Every example imports without keys or network, so you can read the objects it builds in a REPL first.

Decision nodes are recorded: each request emits `decision.*` events with its answers, tokens, latency and cost, so `railtracks viz` shows them and includes their cost in the session totals. Calling `model.aask(...)` directly outside a node is not recorded, the same as calling an LLM directly.

## Errors

| Where | Raised | Catch |
|---|---|---|
| Defining a schema wrongly (an empty schema, 300 Choice options, 1 Score level) | at class definition | `rt.decisions.SchemaDefinitionError` |
| A direct `model.aask(...)` call fails | at call time | `rt.decisions.DecisionProviderError` and its subclasses (`...TimeoutError`, `...RateLimitError`, `...AuthenticationError`, ...) |
| A `decision_node` call fails | at call time | `rt.exceptions.DecisionModelError` and its subclasses, with the provider error as `__cause__` |

Rate limits, timeouts, dropped connections and 5xx responses are retried when the model has a `retry_approach` (see `jev_example.py`); other 4xx responses are not.
