<!--

                       🚀 FEATURE DOCUMENTATION – MCP Integration
================================================================================
Remove comment blocks when no longer needed. Maintain this document as carefully
as you maintain the code: engineers will rely on it to understand, extend, and
operate the feature.

-->

# MCP Integration

Provides first-class, bi-directional integration between RailTracks and the
Model Context Protocol (MCP): *consume* any remote MCP tool as a RailTracks
`Node`, or *expose* any RailTracks `Node` as a FastMCP-compatible tool.

**Version:** 0.0.1

## Table of Contents

- [1. Functional Overview](#1-functional-overview)
  - [1.1 Consuming Remote MCP Tools](#11-consuming-remote-mcp-tools)
  - [1.2 Exposing RailTracks Nodes as MCP Tools](#12-exposing-railtracks-nodes-as-mcp-tools)
  - [1.3 Jupyter / Windows Compatibility](#13-jupyter--windows-compatibility)
- [2. External Contracts](#2-external-contracts)
  - [2.1 Supported Transports](#21-supported-transports)
  - [2.2 Environment Variables & Tokens](#22-environment-variables--tokens)
  - [2.3 CLI Commands](#23-cli-commands)
- [3. Design and Architecture](#3-design-and-architecture)
  - [3.1 Runtime Data-flow (RailTracks ⇒ MCP)](#31-runtime-data-flow-railtracks-⇒-mcp)
  - [3.2 Runtime Data-flow (MCP ⇒ RailTracks)](#32-runtime-data-flow-mcp-⇒-railtracks)
  - [3.3 Threading & Event-Loop Model](#33-threading--event-loop-model)
  - [3.4 Key Design Decisions & Trade-offs](#34-key-design-decisions--trade-offs)
- [4. Related Files](#4-related-files)
  - [4.1 Related Component Files](#41-related-component-files)
  - [4.2 External Dependencies](#42-external-dependencies)
- [CHANGELOG](#changelog)

---

## 1. Functional Overview

The feature is organised around three developer task sets.

### 1.1 Consuming Remote MCP Tools

Connect to any MCP server (HTTP Stream, SSE, or STDIO) and instantly convert
its tools into importable RailTracks `Node` classes that can be invoked inside
agents, graphs, batch pipelines, etc.

```python
from railtracks.rt_mcp import MCPHttpParams
from railtracks.rt_mcp.mcp_tool import connect_mcp
from railtracks.nodes.easy_usage_wrappers.agent import Agent      # Example usage

# 1) Establish a connection ---------------------------------------------------
mcp_server = connect_mcp(
    config=MCPHttpParams(
        url="https://fetch.mcp.ai/streamable-http",      # or "…/sse"
        headers={"Authorization": f"Bearer {MCP_TOKEN}"},
    )
)

# 2) Inspect available tools --------------------------------------------------
for ToolNode in mcp_server.tools:
    print(ToolNode.name())

# 3) Use tools like ordinary Nodes -------------------------------------------
translator = next(t for t in mcp_server.tools if t.name() == "translate")
result     = translator.prepare_tool({"text": "Hello world", "target": "es"}).invoke()
print(result)     # → "Hola mundo"
```

The `MCPServer` object keeps the underlying connection open; close it explicitly
when finished to free resources:

```python
mcp_server.close()
```

### 1.2 Exposing RailTracks Nodes as MCP Tools

Publish your own nodes so they can be consumed by any MCP-compatible client or
LLM agent.

```python
from railtracks.nodes.easy_usage_wrappers.function import function_node
from railtracks.rt_mcp.node_to_mcp import create_mcp_server

# 1) Wrap business logic into a RailTracks Node -------------------------------
@function_node
def add(a: int, b: int) -> int:
    """Return a + b."""

# 2) Create and launch a FastMCP server ---------------------------------------
mcp = create_mcp_server(nodes=[add])
mcp.run(host="0.0.0.0", port=8080, transport="streamable-http")
```

The server now advertises an MCP tool named `add` that accepts JSON input
`{"a": <int>, "b": <int>}` and returns the sum.

### 1.3 Jupyter / Windows Compatibility

On Windows, MCP’s internal process-creation code is incompatible with Jupyter’s
custom I/O streams. Importing `connect_mcp` (or explicitly calling
`railtracks.rt_mcp.jupyter_compat.apply_patches()`) transparently monkey-patches
MCP to work inside notebooks:

```python
from railtracks.rt_mcp.jupyter_compat import apply_patches
apply_patches()   # Safe to call multiple times / no-op on non-Windows.
```

---

## 2. External Contracts

### 2.1 Supported Transports

| Transport            | Endpoint Shape                        | Notes                               |
| -------------------- | ------------------------------------- | ----------------------------------- |
| Streamable-HTTP      | `POST /streamable-http`               | Bidirectional HTTP chunked stream.  |
| Server-Sent Events   | `GET  /sse`                           | One HTTP request per invocation.    |
| STDIO                | Local executable exposing stdin/stdout| Usually used for CLI wrappers.      |

All transports share the same JSON envelope defined by the
MCP specification (see upstream MCP docs).

### 2.2 Environment Variables & Tokens

| Variable                    | Purpose                                          | When Required |
| --------------------------- | ------------------------------------------------ | ------------- |
| `MCP_TOKEN`                 | Bearer token added to `Authorization` header.    | Remote HTTP/SSE servers that require auth. |
| Service-specific variables  | e.g. `OPENAI_API_KEY`, `NOTION_TOKEN`, etc.      | Only when the *server* needs them; not referenced by client-side code. |

### 2.3 CLI Commands

While this feature has no dedicated CLI, typical workflows rely on FastMCP’s
CLI for local servers:

```bash
# Serve current project’s tools on port 8080
python -m mcp.server.fastmcp --host 0.0.0.0 --port 8080
```

---

## 3. Design and Architecture

### 3.1 Runtime Data-flow (RailTracks ⇒ MCP)

```mermaid
flowchart TD
    RT_Node["RailTracks Node<br/>(generated)"] -->|invoke()| MCPAsyncClient
    MCPAsyncClient -->|await| mcp.ClientSession
    ClientSession --> RemoteServer["Remote MCP Server"]
```

1. `connect_mcp` ➜ instantiates `MCPServer`, spinning up a background thread.
2. The thread creates its own asyncio event loop and an `MCPAsyncClient`.
3. Tools are lazily fetched (`list_tools`) and cached.
4. Each `Tool` record from MCP is wrapped by `from_mcp` into a `Node`
   subclass whose `invoke` submits an RPC via `call_tool`.

### 3.2 Runtime Data-flow (MCP ⇒ RailTracks)

```mermaid
flowchart TD
    ExternalClient["MCP Client / LLM"] --> FastMCP["FastMCP Server"]
    FastMCP -->|dispatch tool fn| _create_tool_function
    _create_tool_function -->|await| railtracks.interaction.call
    call --> UserNode["User-defined Node"]
```

`create_mcp_server` converts each `Node` into an asynchronous function that:
1. Validates & orders parameters via `_parameters_to_json_schema`.
2. Delegates execution to the Node’s `prepare_tool` + `call` helper (ensuring
   standardised logging/metrics).

### 3.3 Threading & Event-Loop Model

| Context                  | Thread | Event Loop | Rationale                                           |
| ------------------------ | ------ | ---------- | --------------------------------------------------- |
| Main application         | main   | *any*      | Runs user code, agents, etc.                        |
| `MCPServer` background   | child  | private    | Keeps network I/O off the main loop; avoids deadlocks when the application already owns an asyncio loop (common in Streamlit, Jupyter). |
| `FastMCP` server         | main   | uvicorn loop | Follows FastAPI/Starlette conventions (FastMCP’s implementation). |

Cross-thread invocations use `asyncio.run_coroutine_threadsafe`, enforcing a
timeout derived from `config.timeout`.

### 3.4 Key Design Decisions & Trade-offs

| Decision | Motivation | Trade-offs |
| -------- | ---------- | ---------- |
| **Background thread for `MCPServer`** | Transparent usage from both sync & async user code | Extra complexity; must marshal data across threads. |
| **Lazy tool list caching** | Minimise round-trips on each invocation | Tools added to the remote server after initialisation will not appear unless the user reconnects. |
| **Monkey patch instead of fork/exec shim** | Keep Jupyter support zero-config | Risk of upstream MCP internals changing; mitigated by patch guard checks. |
| **Parameter JSON-Schema translation** | Preserve Node parameter metadata inside FastMCP | Requires dual maintenance of schema mapping helpers. |

---

## 4. Related Files

### 4.1 Related Component Files

- [`components/jupyter_compatibility.md`](../components/jupyter_compatibility.md): Details monkey-patching strategy for notebook environments.
- [`components/mcp_client_server.md`](../components/mcp_client_server.md): Explains the `MCPAsyncClient` / `MCPServer` internal design.
- [`components/mcp_tool_connection.md`](../components/mcp_tool_connection.md): Documents the `connect_mcp` convenience wrapper.
- [`components/node_to_mcp_server.md`](../components/node_to_mcp_server.md): Describes exporting Nodes via `create_mcp_server`.

### 4.2 External Dependencies

- [`https://github.com/modelcontext/mcp`](https://github.com/modelcontext/mcp): Upstream MCP reference implementation.
- [`https://github.com/modelcontext/fastmcp`](https://github.com/modelcontext/fastmcp): FastAPI-based MCP server used by `node_to_mcp_server`.

---

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial public documentation.