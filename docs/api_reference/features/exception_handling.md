<!--
Feature documentation for the *Exception Handling* feature.
Followed the TEMPLATE_FEATURE.md guidelines.
-->

# Exception Handling

Provides a unified error-handling surface that standardizes how failures are represented, enriched, and surfaced across the entire Railtracks runtime—​from low-level model interaction to high-level node orchestration.

**Version:** 0.0.1 <!-- Bump on any externally-observable change. -->

## Table of Contents

- [1. Functional Overview](#1-functional-overview)
- [2. External Contracts](#2-external-contracts)
- [3. Design and Architecture](#3-design-and-architecture)
- [4. Related Files](#4-related-files)
- [CHANGELOG](#changelog)

---

## 1. Functional Overview

At its core, the Exception Handling feature offers:

• A type-safe hierarchy of exceptions (all inheriting from `RTError`) that encode *where* the failure happened and *what* the caller can do about it.  
• Rich, colorised terminal output that highlights root causes and, when available, actionable debugging notes.  
• Centralised, YAML-backed message/notes storage to keep human-readable text decoupled from the code.  
• Specialised helpers for Large Language Model (LLM) errors that capture historical context (`MessageHistory`) for post-mortem analysis.

### 1.1 Unified Error Hierarchy

The top-level `RTError` provides ANSI-colour helpers and establishes the “contract” that every Railtracks exception abides by. All concrete subclasses (e.g. `NodeInvocationError`, `LLMError`) **must** inherit from it, ensuring that downstream code (CLI, web server, notebook widgets) can rely on a single catch-point.

```python
import railtracks as rt
from railtracks.exceptions import NodeInvocationError

try:
    result = rt.call(graph)          # may raise
except NodeInvocationError as exc:
    rt.utils.logging.action.error(exc)   # uniform str(exc) is colourised & note-aware
```

### 1.2 Context-Aware Debug Notes

Most exception constructors accept an optional `notes: list[str]`.  
These notes are appended (green) below the primary error (red) at render-time.

```python
from railtracks.exceptions import NodeCreationError

raise NodeCreationError(
    "Duplicate parameter names detected.",
    notes=[
        "Check that every parameter in `tool_params` is unique.",
        "Hint: autogenerate param keys with `rt.llm.Tool.Parameter.auto_name()`."
    ]
)
```

Output (simplified):

```
❌ Duplicate parameter names detected.
   Tips to debug:
   - Check that every parameter …
   - Hint: autogenerate …
```

### 1.3 LLM Failure Introspection

`LLMError` records the *reason* plus an optional `MessageHistory`. Tools like the Profiler or the Debug UI can pretty-print that history for root-cause analysis.

```python
from railtracks.exceptions import LLMError
from railtracks.llm import MessageHistory

history = MessageHistory.system("You are helpful").user("Hi")
raise LLMError("Model quota exhausted", history)
```

### 1.4 YAML-Driven Message Catalogue

To avoid scattering magic strings, reusable messages live in
`railtracks/exceptions/messages/exception_messages.yaml`.  
They can be fetched via `get_message()` / `get_notes()`:

```python
from railtracks.exceptions.messages import (
    ExceptionMessageKey as Key,
    get_message, get_notes
)

msg  = get_message(Key.OUTPUT_MODEL_REQUIRED_MSG)
notes = get_notes(Key.OUTPUT_MODEL_REQUIRED_NOTES)

raise NodeCreationError(msg, notes)
```

---

## 2. External Contracts

While most of the feature is internal, two artefacts are considered contracts for other systems or teams:

### 2.1 Message Key Catalogue

| File | Stability | Purpose |
|------|-----------|---------|
| `railtracks/exceptions/messages/exception_messages.yaml` | **Stable** | Upstream UIs & docs index keys (e.g. `OUTPUT_MODEL_REQUIRED_MSG`) to show translated copies. Do **not** rename keys without a deprecation cycle. |

### 2.2 CLI / Exit Codes

The Railtracks CLI converts any uncaught `RTError` into process exit code `2`.  
No other exception type should intentionally propagate beyond the boundary.

| Command            | Exit Code | Trigger               |
|--------------------|-----------|-----------------------|
| `python -m railtracks_cli …` | `2` | Any unhandled subclass of `RTError` |

_No environment variables or feature flags currently influence behaviour._

---

## 3. Design and Architecture

### 3.1 Architectural Patterns

• **Single-root Exception Tree** – simplifies `except RTError as e` catch-alls and keeps non-Railtracks errors distinguishable.  
• **Colourised, Human-First Rendering** – leverages ANSI codes defined in `RTError` to draw attention to actionable info.  
• **Externalised Message Content** – messages & notes stored in YAML to enable localisation and runtime overrides without touching code.  
• **Enrichment over Replacement** – concrete classes *wrap* the base class string, never discard context, allowing nested try/except to add details.

### 3.2 Data Flow

```mermaid
flowchart TD
    subgraph Runtime
        A[Graph / Node\nexecution] -->|failure| B(NodeInvocationError)
        A2[Node creation / validation] -->|failure| C(NodeCreationError)
        A3[LLM call] -->|failure| D(LLMError)
        A4[Coordinator timeout] -->|timeout| E(GlobalTimeOutError)
    end

    B & C & D & E --> F(Logger / CLI)
    subgraph Presentation
        F -->|str(exc)| G[[ANSI-colour\nstring]]
    end
```

### 3.3 Key Trade-offs

| Decision | Rationale | Drawback |
|----------|-----------|----------|
| ANSI colours in `__str__` | Quick visual parsing in interactive shells. | Non-TTY sinks (JSON logs, HTTP APIs) must strip escape codes. |
| YAML message store | Simplifies edits & translations. | Runtime overhead of loading YAML once; minimal. |
| Hierarchy depth ≈ 1 | Keeps surface simple (`RTError` children). | Fewer semantic layers; rely on naming to convey nuance. |

### 3.4 Alternatives Considered

1. **Standard Python logging only** – rejected: lacks structured, catchable types; weaker UX.  
2. **Error codes enumerated in code** – rejected: harder to update, less translator-friendly than YAML.  

---

## 4. Related Files

### 4.1 Related Component Files

- [`../components/exception_handling.md`](../components/exception_handling.md): Low-level API & implementation details for all exception classes.
- [`../components/model_error_handling.md`](../components/model_error_handling.md): LLM-specific extensions (`ModelError`, `FunctionCallingNotSupportedError`) that build upon this feature.

### 4.2 Related Feature Files

- [`../logging_profiling.md`](../logging_profiling.md): Shows how exceptions are captured, logged, and profiled across the system.

### 4.3 External Dependencies

- [`https://github.com/yaml/pyyaml`](https://github.com/yaml/pyyaml): Used to parse the YAML message catalogue.

---

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial extraction from component-level docs into formal feature documentation.