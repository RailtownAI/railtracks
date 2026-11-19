# Decision Nodes
A **decision node** asks a decision model a fixed set of questions about a piece of text and returns calibrated probabilities instead of generated text. One request answers every question, typically in well under a second.

Decision models live in `rt.decisions`, the way chat models live in `rt.llm`, and `rt.decision_node` turns a model plus a schema into a node, the way [`rt.agent_node`](overview.md#agent-node) does for an LLM.

## When to Use One
Use a decision node when the output is a judgment you will act on in code: route a ticket, flag a message, grade a reply. Use an `agent_node` with an [`output_schema`](structured_extraction.md) when you need generated content (a summary, extracted fields, free text) or the model has to reason in steps.

| | `decision_node` | `agent_node` with `output_schema` |
|---|---|---|
| Output | A probability per answer | Whatever the LLM writes into your Pydantic model |
| Question types | Yes/no, one of a fixed set of values, a level on a rubric | Any field type |
| Thresholds | Act on `probability >= 0.8` directly | The model's self-reported confidence, if you ask for one |
| Calls | One request for every question | One or more LLM calls |
| Input | Text, or a JSON object or array | Text, images, message history |

## Building a Schema
Each question is an object with a unique `name` and `instructions` telling the model what to decide. There are three kinds:

| Question | Created as | Answer | Read |
|---|---|---|---|
| Yes/no | `rt.decisions.Predicate(name=, instructions=)` | `PredicateAnswer` | `.probability` |
| One of several values | `rt.decisions.Choice(name=, instructions=, choices=)`, 2 to 255 values | `ChoiceAnswer` | `.choice`, `.confidence`, `.probabilities[value]` |
| A level on an ordered rubric | `rt.decisions.Score(name=, instructions=, levels=)`, 2 to 10 levels | `ScoreAnswer` | `.score`, `.confidence`, `.probabilities[index]`, `.legend[index]` |

Group the questions by kind in a `DecisionSchema`:

```python
--8<-- "docs/scripts/documentation/decision_nodes.py:schema"
```

`choices` and `levels` take a list of names, or a mapping of name to a description of when it applies. Levels run from lowest to highest, and a level's index is its score. A question object can be shared by several schemas, but names must be unique within one. A badly defined question or schema (an empty schema, a single level, two questions with one name) raises `rt.decisions.SchemaDefinitionError` as soon as you create it.

## Choosing a Model
Every model answers any `DecisionSchema`, so switching providers is a one-line change. Calls go through `litellm.adecisions`, which reads the key and base URL from the environment at call time, so creating a model never needs a key.

```python
--8<-- "docs/scripts/documentation/decision_nodes.py:models"
```

| Class | Serves | Key | Base URL override |
|---|---|---|---|
| `TypeSafeDecisions` | TypeSafe's Jev models (`jev-latest`) | `TYPESAFE_API_KEY` | `TYPESAFE_API_BASE` |
| `OpenRouterDecisions` | Decision models on OpenRouter (`typesafe/jev-1.13`) | `OPENROUTER_API_KEY` | `OPENROUTER_API_BASE` |
| `OpenAIDecisions` | OpenAI's Decisions API (`gpt-6-luna`, public beta) | `OPENAI_API_KEY` | `OPENAI_BASE_URL`, then `OPENAI_API_BASE` |

Each class also takes `api_key=` and `api_base=` to skip the environment, `timeout=` (seconds per request, default 30) and `retry_approach=`. With no `retry_approach` a model makes one attempt, as chat models do.

```python
--8<-- "docs/scripts/documentation/decision_nodes.py:model_options"
```

## Creating and Running the Node
Pass a name, the model and the schema:

```python
--8<-- "docs/scripts/documentation/decision_nodes.py:node"
```

The node takes one argument, the text to judge, and returns a `DecisionResponse`. Run it through a [Flow](../invocation/flows.md):

```python
--8<-- "docs/scripts/documentation/decision_nodes.py:flow"
```

`str(result)` is a one-line summary with one `name: answer` segment per question. The input can also be a JSON object or array, which is sent to the model as JSON text:

```python
--8<-- "docs/scripts/documentation/decision_nodes.py:json_state"
```

To judge many inputs at once, call the node with `rt.call_batch` inside another node. The calls run in parallel:

```python
--8<-- "docs/scripts/documentation/decision_nodes.py:batch"
```

## Reading the Answers
Index `result.structured` with a question object to get its typed answer, so your editor knows `result.structured[department]` is a `ChoiceAnswer`. Indexing with the question's name (`result.structured["department"]`) also works, untyped.

```python
--8<-- "docs/scripts/documentation/decision_nodes.py:answers"
```

!!! tip "Act on the probabilities"
    The answers are calibrated, so a threshold means what it says: an answer given at `0.8` is wrong about one time in five. Pick the threshold from the cost of a mistake, and send anything below it to a person or a slower path.

`ScoreAnswer.score` is the probability-weighted level, so it can fall between levels (`1.4` on a 0 to 2 rubric). `.probabilities` holds the probability of each level, and `.legend` maps each level index back to its label.

## Using It as an Agent Tool
A decision node is a tool, so you can pass it in an agent's `tool_nodes`. The agent sends the text as the tool's `state` argument and reads the `str()` summary. The tool description lists each question's instructions; pass `description=` to `decision_node` to write your own.

```python
--8<-- "docs/scripts/documentation/decision_nodes.py:agent_tool"
```

## Handling Errors
A failed call inside a decision node raises `rt.exceptions.DecisionModelError`, a `NodeInvocationError` like `LLMError`, with the model's own error kept as `__cause__`. Catch a subclass to handle one case:

| Error | Raised when | Retry? |
|---|---|---|
| `DecisionTimeoutError` | The model didn't answer within `timeout` | Usually transient |
| `DecisionRateLimitError` | The provider rejected the call for rate or quota reasons | Back off first |
| `DecisionAuthenticationError` | The API key is missing or was rejected | No; fix the key |
| `DecisionRefusalError` | The model declined one or more questions (OpenAI can) | No |
| `DecisionModelError` | Anything else: a dropped connection, another 4xx or 5xx status, an unparseable response | Depends |

A `DecisionRefusalError` keeps the answers the model did give: `.refused` names the declined questions and `.answers` holds the rest, keyed by name.

```python
--8<-- "docs/scripts/documentation/decision_nodes.py:errors"
```

Only litellm's API errors are mapped to these classes; any other litellm exception, such as a budget or guardrail error from litellm itself, propagates unchanged.

### Retrying
Set `retry_approach=` on the model, as shown in [Choosing a Model](#choosing-a-model). Rate limits, timeouts, dropped connections and 500 and 503 responses are then retried inside the call, before the node raises anything. A rejected key, a refusal and other 4xx responses are not retried.

`middleware=[Retry()]` with its defaults does **not** retry a decision node. `Retry`'s default `retry_on` lists litellm's raw exceptions, and by the time an error leaves the node it has already become a `DecisionTimeoutError` or `DecisionRateLimitError`. To retry at the node level instead, name the node's errors:

```python
--8<-- "docs/scripts/documentation/decision_nodes.py:retry_node"
```

Once every attempt fails, `Retry` raises `rt.llm.RetryError`, with each attempt's error in `.exception_list`. That is not a `DecisionModelError`, so catch it separately. Use `retry_approach=` on the model if you want the node to keep raising a `DecisionModelError` subclass after the retries run out.

??? note "Calling the model directly"
    Outside a node you can call the model yourself with `await model.aask(state, schema)`, as you would call an LLM's `achat`. A direct call raises the model-layer errors instead: `rt.decisions.DecisionProviderError` and its `DecisionProviderTimeoutError`, `DecisionProviderRateLimitError`, `DecisionProviderAuthenticationError` and `DecisionProviderRefusalError` subclasses. It is also not recorded.
    ```python
    --8<-- "docs/scripts/documentation/decision_nodes.py:direct"
    ```

## Cost and Recorded Events
Every `DecisionResponse` carries `model_name` (as the provider reports it), `provider`, `input_tokens`, `output_tokens`, `latency` and `cost` in USD:

```python
--8<-- "docs/scripts/documentation/decision_nodes.py:cost"
```

`cost` is litellm's price for the call, and `None` when litellm can't price the model. `OpenAIDecisions` prices input tokens only, since the Decisions API bills input tokens alone.

Each request made by a decision node is recorded as `decision.*` events, so [`railtracks viz --beta`](../../observability/agenthub/local_v2.md) shows it under the node with its answers, tokens, latency and cost, and includes its cost in the session totals:

| Event | Recorded |
|---|---|
| `decision.invocation` | Before the request: the model, the input and the questions |
| `decision.response` | After it: the answers, reported model and provider, tokens, cost and latency |
| `decision.failure` | Instead of a response, when the call fails: the model's error before it becomes a `DecisionModelError` |

!!! note "Evaluations"
    [Evaluations](../../evaluations/quickstart.md) count LLM calls only, so decision cost is not part of the `TokenCost` the [`LLMInferenceEvaluator`](../../evaluations/evaluators/llm_inference_evaluator.md) reports.

## Limitations
- **Text only.** The input is a string, or a JSON object or array sent as JSON text. Images and other attachments are not supported yet.
- **No model middleware.** A decision node makes no LLM call, so passing model-only middleware (`pre_llm`, `post_llm` or `wrap_llm` middleware, an LLM guardrail, or `ContextInjection`) raises `NodeCreationError`. Node middleware works: your own `rt.wrap_node` and `rt.post_node` middleware, and prebuilt middleware that works in either slot, such as `Retry`, `MaxCalls` and `Timeout`, which then wraps the whole node call. Only `decision_node` checks this: `rt.couple` on an already-built decision node accepts model middleware without complaint, so it is silently ignored under `model_middleware=` and fails only when the node runs under `middleware=`.

```python
--8<-- "docs/scripts/documentation/decision_nodes.py:node_middleware"
```

For a runnable end-to-end version, see [`examples/s1/s1_demo.py`](https://github.com/RailtownAI/railtracks/blob/main/examples/s1/s1_demo.py).
