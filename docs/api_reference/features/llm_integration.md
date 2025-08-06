<!--
                         FEATURE DOCUMENTATION
=============================================================================

Authoring notes:
• Follow TEMPLATE_FEATURE.md guidance.
• Keep explanations high-level here; component-level details live in their own
  docs and are linked where needed.
• Update CHANGELOG on any externally observable change.
-->

# LLM Integration

End-to-end framework that embeds Large-Language-Model (LLM) capabilities into the Railtracks runtime—covering messaging, model invocation, provider abstraction, prompt handling, error handling, and a minimal chat UI.

**Version:** 0.0.1 <!-- bump on any externally-observable change -->

---

## Table of Contents

- [1. Functional Overview](#1-functional-overview)
- [2. External Contracts](#2-external-contracts)
- [3. Design and Architecture](#3-design-and-architecture)
- [4. Related Files](#4-related-files)
- [CHANGELOG](#changelog)

---

## 1. Functional Overview

The feature exposes a cohesive set of task-sets that, together, allow developers to:

1. Build, inspect, and manipulate conversation histories.
2. Invoke local or cloud LLMs—synchronously, asynchronously, or in streaming mode.
3. Extend support for new providers with minimal boiler-plate.
4. Inject contextual data into prompts at runtime.
5. Surface model errors in a structured way.
6. Embed a reference browser-based chat UI for rapid prototyping and demos.

The following subsections outline each task-set from a user’s perspective.

### 1.1 Messaging & History Management

Create strongly-typed messages, append them to a history, and pre-process them before sending to a model.

```python
from railtracks.llm.message import UserMessage, AssistantMessage, SystemMessage
from railtracks.llm.history import MessageHistory
from railtracks.utils.prompt_injection import inject_values, ValueDict

history = MessageHistory([
    SystemMessage("You are a helpful assistant."),
    UserMessage("What’s the weather in Paris?"),
])

# Dynamically inject runtime values into the prompt placeholders
inject_values(history, ValueDict(city="Paris"))

print(history.removed_system_messages())
```

For message semantics, roles, and helper methods see [`components/llm_messaging.md`](../components/llm_messaging.md).

### 1.2 Model Invocation (Chat / Structured / Streaming)

Interact with any `ModelBase` implementation (local or cloud) using a uniform API.

```python
from railtracks.llm.model import ModelBase
from railtracks.llm.history import MessageHistory
from railtracks.llm.models.api_providers.openai import OpenAILLM

# ❶ Pick a provider wrapper
llm: ModelBase = OpenAILLM(model_name="gpt-3.5-turbo")

# ❷ (Optional) attach hooks
llm.add_pre_hook(lambda messages, **kw: print("→", messages))
llm.add_post_hook(lambda resp, **kw: print("←", resp.message().content))

# ❸ Call any of the high-level helpers
history = MessageHistory().append(UserMessage("Say hello!"))
resp   = llm.chat(messages=history)             # regular chat
async_resp = await llm.achat(messages=history)  # async
stream = llm.stream_chat(messages=history)      # generator of chunks
```

Structured outputs via Pydantic schemas are handled through `structured()` / `astructured()`.  
Detailed API surface documented in [`components/model_interaction.md`](../components/model_interaction.md).

### 1.3 Provider Abstraction (Cloud & Local)

Switch between different providers without changing call-sites.

```python
from railtracks.llm.models.cloud.azureai import AzureAILLM
from railtracks.llm.models.local.ollama import OllamaLLM

cloud_llm  = AzureAILLM("gpt-35-turbo")
local_llm  = OllamaLLM("mistral", domain="auto")

for model in (cloud_llm, local_llm):
    print(model.model_type(), "→", model.chat(messages=history).message().content)
```

New providers only need to subclass `ProviderLLMWrapper`; see [`components/api_provider_wrappers.md`](../components/api_provider_wrappers.md).

### 1.4 Prompt Formatting & Context Injection

Fill placeholders in prompt templates or entire histories using runtime context.

```python
from railtracks.utils.prompt_injection import fill_prompt

template = "Hello {user_name}, today is {date}."
runtime_values = ValueDict(user_name="Alice", date="2024-05-12")
print(fill_prompt(template, runtime_values))
# → "Hello Alice, today is 2024-05-12."
```

More examples & gotchas in [`components/prompt_formatting.md`](../components/prompt_formatting.md).

### 1.5 Error Handling

Catch and reason about model-specific failures via typed exceptions.

```python
from railtracks.llm.models._model_exception_base import FunctionCallingNotSupportedError

try:
    resp = cloud_llm.chat_with_tools(history, tools=[...])
except FunctionCallingNotSupportedError as e:
    logger.warning("Fallback to manual handling: %s", e)
```

Error taxonomy is defined in [`components/model_error_handling.md`](../components/model_error_handling.md).

### 1.6 Reference Chat UI

Spin up a lightweight FastAPI server to interact with any `ModelBase` instance.

```bash
python -m railtracks.utils.visuals.browser.chat_ui
# Navigate to http://localhost:8000 to start chatting
```

Integration guidance & available REST endpoints in [`components/chat_ui.md`](../components/chat_ui.md).

---

## 2. External Contracts

### 2.1 Environment Variables

| Name                         | Description                                               | Default     |
| ---------------------------- | --------------------------------------------------------- | ----------- |
| `OPENAI_API_KEY`            | API key for OpenAI provider wrappers                      | —           |
| `AZURE_OPENAI_ENDPOINT` & `AZURE_OPENAI_KEY` | Required for `AzureAILLM`                    | —           |
| `OLLAMA_HOST`               | When using `OllamaLLM(domain="auto")`, host of Ollama srv | `localhost` |
| `RAILTRACKS_PROMPT_INJECTION`| Toggle context-prompt injection globally (`true`/`false`) | `true`      |

Component-level docs specify additional env-vars where relevant.

### 2.2 CLI Entry Points

| Command                         | Description                                | Owned By |
| ------------------------------- | ------------------------------------------ | -------- |
| `python -m railtracks.utils.visuals.browser.chat_ui` | Launches reference chat UI | Feature |

### 2.3 Events & Pub/Sub

This feature does **not** publish/subscribe to system-wide events directly; instead individual components (e.g. [`pubsub_messaging`](../components/pubsub_messaging.md)) handle that.

---

## 3. Design and Architecture

LLM Integration stitches together multiple slow-changing component contracts. The high-level design is shown in the following Mermaid diagram.

```mermaid
flowchart LR
    subgraph "User / Developer"
        A[MessageHistory] -->|chat()/structured()| B(ModelBase)
    end

    %% Core
    B --> C[Provider Wrapper<br/>(cloud/local)]
    C --> D[LiteLLMWrapper] -->|invokes| E[litellm\n3rd-party]
    B --> F[Hook Pipeline]
    B -.->|raises| G[ModelError Hierarchy]

    %% Prompt handling
    H[Prompt Formatter] --> I[inject_values()]
    I --> A

    %% UI
    J[Chat UI (FastAPI)] --> A
    J --> B
    
    style B fill:#FFF5D1,stroke:#FFB700
```

Key points:

1. **Abstraction Layers**  
   • `Message`/`MessageHistory` → **conversation semantics**  
   • `ModelBase` → **capabilities contract** (sync, async, streaming, structured)  
   • `ProviderLLMWrapper` → **provider-specific translation**  
   • `LiteLLMWrapper` → leverage [`litellm`](https://github.com/BerriAI/litellm) for transport & token counting.  

2. **Hook Pipeline**  
   Pre-, post-, and exception-hooks provide cross-cutting concerns (logging, retry, redaction) without subclassing.

3. **Prompt Life-Cycle**  
   At runtime, context variables are injected before the hook pipeline, guaranteeing downstream model calls see concrete strings.

4. **Error Boundaries**  
   All provider/network errors are mapped to the `ModelError` hierarchy. The caller only imports component-specific exceptions when they need fine-grained handling.

5. **Extensibility**  
   Adding a new provider = one subclass + optional overrides:
   ```python
   class GroqLLM(ProviderLLMWrapper):
       @classmethod
       def model_type(cls) -> str: return "Groq"
   ```
   No other code changes needed.

6. **UI Separation**  
   The Chat UI remains an optional, stateless visualization layer. It communicates over HTTP POST + Server-Sent Events, keeping the core package headless.

### 3.1 Performance & Scalability Choices

- Hook execution is synchronous by design to keep ordering deterministic; heavy work should happen in async hooks or external services.
- Large message histories are trimmed by upstream business logic (not by this feature) to avoid provider-side token limits.
- Streaming API surfaces a Python generator (`Response.streamer`) to allow back-pressure in caller code.

### 3.2 Rejected Alternatives

- **Direct SDKs per provider** — increased maintenance overhead; `litellm` already abstracts 10+ providers and is battle-tested.  
- **Prompt injection via Jinja** — brings template-rendering edge cases; key-only `string.Formatter` proved simpler and safer.

---

## 4. Related Files

### 4.1 Related Component Files

- [`components/llm_messaging.md`](../components/llm_messaging.md) – message & history primitives.
- [`components/model_interaction.md`](../components/model_interaction.md) – `ModelBase` and hook pipeline.
- [`components/api_provider_wrappers.md`](../components/api_provider_wrappers.md) – cloud provider abstraction.
- [`components/cloud_model_wrappers.md`](../components/cloud_model_wrappers.md) – Azure OpenAI wrapper specifics.
- [`components/local_model_wrappers.md`](../components/local_model_wrappers.md) – Ollama/local wrapper specifics.
- [`components/prompt_injection.md`](../components/prompt_injection.md) – context injection logic.
- [`components/prompt_formatting.md`](../components/prompt_formatting.md) – formatting helpers.
- [`components/model_error_handling.md`](../components/model_error_handling.md) – custom exception hierarchy.
- [`components/chat_ui.md`](../components/chat_ui.md) – browser UI integration.

### 4.2 Related Feature Files

_No additional feature files are currently dependent on LLM Integration; other high-level features should link back here._

### 4.3 External Dependencies

- [`https://github.com/BerriAI/litellm`](https://github.com/BerriAI/litellm) – provider-agnostic LLM client (MIT).
- [`https://fastapi.tiangolo.com`](https://fastapi.tiangolo.com) – powering the reference chat server.

---

## CHANGELOG

- **v0.0.1** (2024-05-12) [`<INITIAL>`]: Initial public documentation.