# System One (S1) decision examples

System One models read a piece of text and answer typed questions about it with calibrated probabilities instead of prose: a yes/no (`Predicate`), a pick from named values (`Choice`), or a level on a rubric (`Score`). One request answers every question in a single forward pass. In railtracks the models live in `rt.decisions`, the way chat models live in `rt.llm`, and `rt.decision_node` turns a model plus a schema into a node, the way `rt.agent_node` does for an LLM.

- `s1_demo.py` -> start here. Triages a support inbox with Jev: one ticket through a Flow, a whole inbox routed on the probabilities (confident tickets go to a team queue, unclear ones to a person), the decision as an agent's tool, and a direct `aask` call with a JSON state. Swapping vendors is a one-line change at the top.
- `jev_example.py`, `openrouter_example.py`, `openai_example.py` -> the same triage schema and Flow on each vendor, one file per vendor.

## Vendors

Every vendor answers the same `rt.decisions.DecisionSchema`, so switching is a one-line change.

| Class | Serves | Key | Notes |
|---|---|---|---|
| `TypeSafeAI` | TypeSafe's Jev (`jev-latest`) | `TYPESAFE_API_KEY` (required) | `TYPESAFE_API_BASE` overrides the URL; text and JSON input only |
| `OpenRouterAI` | System One models on OpenRouter (`typesafe/jev-1.13`) | `OPENROUTER_API_KEY` (required) | `OPENROUTER_API_BASE` overrides the URL; text and JSON input only |
| `OpenAIDecisions` | OpenAI's Decisions API (`gpt-6-luna`, public beta) | `OPENAI_API_KEY` (required) | `OPENAI_BASE_URL` overrides the URL; also accepts images; bills input tokens only |

Each class also takes `api_key=`, `api_base=`, `timeout=` (seconds, default 30) and `retry_approach=`.

## The schema

Subclass `DecisionSchema` and declare each question as a class attribute; the attribute name is the question's name.

| Question | Declared as | Answer | Read |
|---|---|---|---|
| Yes/no | `Predicate(instructions=)` (alias `Noul`) | `PredicateAnswer` | `.probability` |
| One of several values | `Choice(instructions=, choices={value: description} or [values])`, 2 to 255 values | `ChoiceAnswer` | `.choice`, `.confidence`, `.probabilities[value]` |
| A level on an ordered rubric | `Score(instructions=, levels={label: criteria} or [labels])`, 2 to 10 levels | `ScoreAnswer` | `.score` (expected level index), `.confidence`, `.probabilities[index]`, `.legend[index]` |

On a response, `result.structured.<name>` is typed as that question's answer, and `str(result)` is the one-line summary an agent reads (`is_urgent: yes 0.99 | department: technical 1.00 | frustration: 2.0/2`).

## How routing works

Every call goes through `litellm.adecisions`, the way chat models go through litellm's completion API. railtracks always sends OpenAI's request shape (`input` plus a list of named `questions`) with the model as `"<vendor>/<model>"` (`typesafe/jev-latest`, `openrouter/typesafe/jev-1.13`, `openai/gpt-6-luna`); litellm translates it to each vendor's own API, reads the key and base URL from the environment variables above, and returns OpenAI's response shape, which railtracks parses into your schema. The result's `cost` is litellm's price for the call. Images are only accepted by OpenAI; a System One vendor rejects them before anything is sent.

## Running them

```bash
uv run python examples/s1/s1_demo.py
uv run python examples/s1/openrouter_example.py
```

Each example needs its vendor's key in your environment (see the table); `s1_demo.py` also needs `OPENAI_API_KEY` for the agent. Every example imports without keys or network, so you can read the objects it builds in a REPL first.

Decision nodes are recorded: each request emits `decision.*` events with its answers, tokens, latency and cost, so `railtracks viz` shows them and includes their cost in the session totals. Calling `model.aask(...)` directly outside a node is not recorded, the same as calling an LLM directly.

## Errors

| Where | Raised | Catch |
|---|---|---|
| Defining a schema wrongly (an empty schema, 300 Choice values, 1 Score level) | at class definition | `rt.decisions.SchemaDefinitionError` |
| A direct `model.aask(...)` call fails | at call time | `rt.decisions.DecisionProviderError` and its subclasses (`...TimeoutError`, `...RateLimitError`, `...AuthenticationError`, `...ConnectionError`, `...ServerError`, `...RequestError`, ...) |
| A `decision_node` call fails | at call time | `rt.exceptions.DecisionModelError` and its subclasses, with the provider error as `__cause__` |
| The model declines a question (OpenAI can) | at call time | `rt.decisions.DecisionProviderRefusalError` (direct) / `rt.exceptions.DecisionRefusalError` (node); `.refused` names the questions, `.answers` holds the ones it did answer |

litellm's exceptions are mapped to these classes, so you never need to catch a litellm type. Rate limits, timeouts, dropped connections and 5xx responses are retried when the model has a `retry_approach` (see `jev_example.py`); a rejected key, a refusal and other 4xx responses are not.
