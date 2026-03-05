# Flows (Session Management)
In Railtracks, flows are the primary way to organize your agent runs. Think of a Flow as a blueprint that you invoke to start a run. A single Flow can be invoked multiple times to execute the same agentic process. This guide provides concrete examples to help you get started with Flows.

## Quickstart
To get started with Flows, you simply need to provide an entry point and a name.

```python
--8<-- "docs/scripts/flows_sessions.py:quickstart"
```

## Passing Configuration
If you want to apply configurations scoped to a specific Flow, you can pass them in during the Flow's creation.

```python
--8<-- "docs/scripts/flows_sessions.py:passing_configurations"
```

## Injecting Context
Sometimes you may want generic context items to be available across all runs of a Flow. In other cases, you might want context scoped to a specific run (or injected at runtime).

```python
--8<-- "docs/scripts/flows_sessions.py:injecting_context"
```

!!! warning
    The context dictionaries used by Flows are passed by value. If a specific run mutates its context dictionary, those changes will not affect the original context or be passed to other runs.