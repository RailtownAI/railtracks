<!--
Feature Documentation – Logging and Profiling
=============================================================================

Authoring notes:
•  Place this file at docs/raw/features/logging_profiling.md
•  Keep links relative to *this* file (one level up to components/, two to other
   features/, etc.).
•  Do NOT trim the HTML comments—they are here for future maintainers.
-->

# Logging and Profiling

A unified observability layer that offers fine-grained logging and lightweight runtime profiling to help developers debug, audit, and optimise Railtracks applications.

**Version:** 0.0.1 <!-- Bump on any externally-observable change. -->

## Table of Contents

- [1. Functional Overview](#1-functional-overview)  
  – 1.1 Task Set A: Runtime Logging  
  – 1.2 Task Set B: Performance Profiling
- [2. External Contracts](#2-external-contracts)
- [3. Design and Architecture](#3-design-and-architecture)
- [4. Related Files](#4-related-files)
- [CHANGELOG](#changelog)

---

## 1. Functional Overview

Logging and Profiling is intentionally split into two task sets:

| Task Set | Key Audience | Typical Questions Answered |
|----------|--------------|----------------------------|
| **Runtime Logging** | Developers & Operators | “What happened?” / “Why did this fail?” |
| **Performance Profiling** | Performance Eng. & Researchers | “How long did each step take?” |

Below we show the most common entry points and usage patterns.  For complete
parameter references, see the component documentation linked in each section.

### 1.1 Task-Set A – Runtime Logging

Railtracks exposes a single configuration surface—`ExecutorConfig`—and a
namespaced logger hierarchy rooted at `RT`.  Together they provide out-of-box
terminal logging, optional file logging, coloured output, and pluggability for
custom handlers.

```python
import railtracks as rt
from railtracks.utils.logging.create import get_rt_logger

################################################################################
# 1️⃣  Configure logging *once* at application start-up.                        #
################################################################################
cfg = rt.ExecutorConfig(
    logging_setting="VERBOSE",    # VERBOSE / REGULAR / QUIET / NONE
    log_file="my_run.log",        # optional file sink
)
rt.set_config(cfg)                # Apply globally (or use `with rt.Session` …)

################################################################################
# 2️⃣  Obtain loggers and write messages.                                       #
################################################################################
root_logger = get_rt_logger()              # "RT"
worker_logger = get_rt_logger("worker-42") # "RT.worker-42"

root_logger.info("initialising")
worker_logger.debug("internal state=%s", some_dict)

################################################################################
# 3️⃣  Leverage structured action logs for graph execution.                     #
################################################################################
from railtracks.utils.logging.action import (
    RequestCreationAction,
    RequestSuccessAction,
    RequestFailureAction,
)

root_logger.info(RequestCreationAction(
    parent_node_name="Coordinator",
    child_node_name="Chunker",
    input_args=("doc.txt",),
    input_kwargs={}
).to_logging_msg())
```

Key capabilities
•  Four opinionated log levels (VERBOSE, REGULAR, QUIET, NONE)  
•  Colourised console output via `ColorfulFormatter` for fast visual scanning  
•  Optional timestamped file output (`log_file="*.log"`)  
•  Namespaced loggers (`RT.<subsystem>.<module>…`) keep 3rd-party code isolated  
•  Structured messages for node life-cycle events (see
  `../components/logging_actions.md`)

Further reading: `docs/observability/logging.md` for detailed workflow examples
and guidance on forwarding logs to external providers (Sentry, Loggly, etc.).

### 1.2 Task-Set B – Performance Profiling

The **Profiling** sub-system delivers a zero-dependency mechanism to annotate
and retrieve execution “stamps”.  Each `Stamp` captures:

```
time  – float   (epoch seconds)
step  – int     (logical order)
id    – str     (human message, e.g., "chunking complete")
```

```python
from railtracks.utils.profiling import StampManager

###############################################################################
# 1️⃣  Create a manager and record stamps.                                     #
###############################################################################
sm = StampManager()

sm.create_stamp("Session start")
tokeniser_stamp = sm.create_stamp("Doc tokenised")   # increments step each call

###############################################################################
# 2️⃣  Grouped stamps: keep the same ‘step’ for related sub-events.            #
###############################################################################
group = sm.stamp_creator()          # freeze current step
group("chunk-A embedded")
group("chunk-B embedded")

###############################################################################
# 3️⃣  Export data for visualisation / debugging.                              #
###############################################################################
timeline = sm.all_stamps            # total ordering by step then time
step_map = sm.step_logs             # Dict[int, List[str]]
```

Because `StampManager` is thread-safe and serialisable (`__getstate__`,
`__setstate__`), it can be propagated through distributed tasks or pickled into
reports for post-hoc analysis.

---

## 2. External Contracts

| Type | Name / Endpoint | Description | Notes |
|------|-----------------|-------------|-------|
| Environment Var | _N/A_ | Logging level and file output are deliberately configured in-code to avoid unexpected production overrides. | Explicit design choice—see Design §3.2 |
| CLI | `python -m railtracks …` | Inherits logging configuration from `ExecutorConfig` when initialising a CLI `Session`. | See `features/cli_interface.md` |
| Python API | `get_rt_logger()` | Returns a logger compliant with `logging.Logger`. | Link: `../components/logger_creation.md` |
| Event | Structured log message string | Consumers (AIOLogstash, Fluentd, etc.) may tail the file handler or stdout. | The message grammar is defined in `logging.actions` |

Should future integrations require environment toggles (e.g., `RT_LOG_LEVEL`),
they must be added to this contract table and the configuration pipeline (see
Design §3.4).

---

## 3. Design and Architecture

### 3.1 Architectural Overview

```mermaid
flowchart TD
    subgraph Logging
        EC[ExecutorConfig] -->|calls| LC[prepare_logger()]
        LC --> RTLogger[RT root logger]
        RTLogger --> CH[ConsoleHandler]
        RTLogger --> FH[FileHandler?]
        RTLogger --> SH[StructuredAction msgs]
    end

    subgraph Profiling
        StampManager --> Stamp
        StampManager -->|serialize| Reports
    end

    classDef dashed stroke-dasharray: 4 4
    Reports-. external tooling .-> Grafana
```

•  **Centralised bootstrap** (`ExecutorConfig.prepare_logger`) ensures all code
   paths share a single `logging.Logger` hierarchy.  
•  **Colourised console output** implemented in
  `ColorfulFormatter.format(record)`—keeps ANSI details out of business logic.  
•  **Structured action logging** decouples node life-cycle semantics from
  presentation; the stringification (`to_logging_msg`) is the only
  presentation-layer knowledge the logger needs.  
•  **Profiling** is purposely orthogonal; it does not emit log lines but can be
  consumed by the logging sub-system or by external visualisers.

### 3.2 Guiding Principles

| Principle | Applied To | Resulting Trade-off |
|-----------|------------|---------------------|
| **Minimal global mutable state** | Logger config is held in `logging` module only | Simpler concurrency story; requires explicit early configuration |
| **Fail-fast misconfiguration** | Invalid `logging_setting` raises `ValueError` | Safe defaults over silent errors |
| **Low overhead profiling** | `Stamp` is a dataclass; dict copies in getters | O(1) creation, but large logs may require post-processing for memory |
| **Human-first logs** | Colourful, action verbs (CREATED/DONE/FAILED) | Log parsing requires colour stripping when exporting |

### 3.3 Alternative Designs Considered

1. **Third-party logging frameworks (Loguru, structlog)** – Rejected to avoid
   additional transitive dependencies and keep interoperability with Python’s
   standard library.
2. **`tracemalloc` / cProfile for profiling** – Valuable for deep performance
   analysis but too heavyweight for day-to-day operator needs.  `StampManager`
   hits the 80-20 use-case.

### 3.4 Extensibility Hooks

•  **Custom Handlers** – Import `logging.Handler` subclasses and attach them
  after `prepare_logger()`:

```python
from railtracks.utils.logging.create import get_rt_logger
from mycompany.logging import SlackHandler

logger = get_rt_logger()
logger.addHandler(SlackHandler(token="…"))
```

•  **Formatter Plug-in** – Replace `ColorfulFormatter` with any
  `logging.Formatter` compliant object at runtime.

•  **Profiling Aggregators** – Stamps can be JSON-serialised and shipped to
  observability back-ends (Grafana Tempo, Honeycomb, etc.).

---

## 4. Related Files

### 4.1 Related Component Files

- [`../components/executor_configuration.md`](../components/executor_configuration.md)  
  – Primary entry point for user-facing logging configuration (`ExecutorConfig`).
- [`../components/logging_configuration.md`](../components/logging_configuration.md)  
  – Implementation details for colourised console, file handlers, and log levels.
- [`../components/logger_creation.md`](../components/logger_creation.md)  
  – Explains `get_rt_logger` and logger naming conventions.
- [`../components/logging_actions.md`](../components/logging_actions.md)  
  – Describes structured log action classes for request lifecycle events.
- [`../components/profiling.md`](../components/profiling.md)  
  – Covers `Stamp`, `StampManager`, and thread-safety guarantees.

### 4.2 Related Feature Files

- [`./cli_interface.md`](./cli_interface.md)  
  – CLI sessions automatically pick up global logging settings.
- [`./state_management.md`](./state_management.md)  
  – Persisted state may include `StampManager` snapshots for offline analysis.

### 4.3 External Dependencies

- [`https://pypi.org/project/colorama/`](https://pypi.org/project/colorama/)  
  – ANSI colour support for cross-platform console logging.

---

## CHANGELOG

- **v0.0.1** (2024-06-11) [`<COMMIT_HASH>`]: Initial feature documentation.