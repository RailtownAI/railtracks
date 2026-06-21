# Railtracks Python → .NET port

A .NET 8 port of the Python `railtracks` framework (`packages/railtracks/src` + `tests`).
Scope is strictly the core framework — `docs/`, `scripts/`, `examples/`, `pdoc/` are excluded.

## Layout

```
dotnet/
  Railtracks.sln
  Directory.Build.props              # net8.0, nullable, langversion 12, common metadata
  src/Railtracks.Core/               # the framework
    Exceptions/                      # RTError -> RailtracksException
    Llm/                             # LLM domain (content, messages, model, ...)
    Llm/Tools/                       # Parameter model, Tool, schema/docstring parsers
  tests/Railtracks.Core.Tests/       # xUnit + Moq + FluentAssertions
  DEPENDENCY_MAP.md
```

## NuGet dependency mapping

| Python package | Role | .NET / NuGet equivalent | Notes |
|---|---|---|---|
| `litellm` | Unified gateway over ~100 LLM providers | **`Microsoft.Extensions.AI`** (`IChatClient`) | No single 1:1 NuGet. Concrete model adapters bind to `IChatClient` (OpenAI / Azure / Anthropic / Ollama). |
| `pydantic` | Models + JSON-schema generation + validation | `System.Text.Json` (+ `System.ComponentModel.DataAnnotations` / `JsonSchema.Net` when needed) | Schema parsing ported manually in `SchemaParser`. |
| `mcp` | Model Context Protocol | `ModelContextProtocol` (official C# SDK) | For the MCP slice. |
| `PyYAML` | Config / attachment-format table | `YamlDotNet` | Attachment magic-byte table inlined for now. |
| `colorama` / `rich` | Terminal color/formatting | `Spectre.Console` (optional) | ANSI codes inlined in exception base. |
| `python-dotenv` | `.env` loading | `DotNetEnv` | For the `Session` slice. |
| `tiktoken` | Token counting | `Microsoft.ML.Tokenizers` | Retrieval slice (excluded for now). |
| `scikit-learn` / `chromadb` | Embeddings / vector store | TBD (`Microsoft.Extensions.AI` embeddings + a vector DB client) | Retrieval slice (excluded for now). |
| `pytest` | Test framework | **xUnit** + **Moq** + **FluentAssertions** | |

## Idiom translations

- Python `async` generators / sync+async overloads → async-first `Task<T>` methods. Streaming
  (`Generator`/`Stream`) is deferred; `IAsyncEnumerable<T>` is the planned shape.
- Decorators / `function_node` (arbitrary callables → typed tool-nodes) → reflection-based
  `Tool.FromMethod` / `FromDelegate` (no runtime docstrings, so descriptions are passed explicitly).
- pydantic `BaseModel` content union → typed `Message` subclasses with `object Content`.
- Python `str`-valued enums (`Role`, `ModelProvider`, `ParameterType`) → C# enums + a `.Value()`
  extension preserving the wire string (e.g. `Gemini` → `"Vertex_AI"`).
- Monkeypatched `urllib` in tests → injectable delegates (`AttachmentEncoding.UrlFetcher`,
  `Attachment.UrlProbe`) so tests stay offline.

## Status — Slice 1 (foundation, COMPLETE, 102 tests green)

Ported & tested:
- `Exceptions`: `RailtracksException` (RTError), `LlmException` (RTLLMError), `RetryException`, `ToolCreationException`.
- `Llm`: `Role`, `ModelProvider`, `ToolCall`, `ToolResponse`, `Stream<T>`, `Message` hierarchy
  (`UserMessage`/`SystemMessage`/`AssistantMessage`/`ToolMessage`), `Attachment` + `AttachmentEncoding`,
  `PromptInjection`, `MessageHistory`, `MessageInfo`, `Response`, `ModelBase` (hook orchestration).
- `Llm.Tools`: `ParameterType`, `Parameter` + `Array`/`Object`/`Ref`/`Union` subclasses,
  `DocstringParser`, `SchemaParser`, `Tool` (+ reflection builder).

Mapped 1:1 from these Python tests:
`test_content`, `test_message` (offline), `test_history`, `test_response`,
`test__base`, `test_array/object/ref/union_parameter`, `test_schema_parser`, `test_docstring_parser`,
plus a `ModelBase` hook suite and a `Tool.FromMethod` suite.

## Roadmap — remaining slices (module-by-module, on this foundation)

2. **Concrete models** — `Microsoft.Extensions.AI` adapter implementing `ModelBase`
   (`type_mapping`, `retries`, provider adapters). Port `test_model`, `test_retries`, `test_litellm_wrapper`.
3. **Nodes & execution** — `Node`/`ToolCallable`/`ToolManifest`, `function_node`/`agent_node`,
   `execution`, `pubsub`, `state`, `context`, `Session`, `interaction` (`call`/`broadcast`/`call_batch`).
4. **Orchestration** — `Flow`.
5. **Feature modules** — `guardrails`, `evaluations`, `human_in_the_loop`, `prebuilt`, `integrations`, `rt_mcp`.
6. **Retrieval** (opt-in extra) — `retrieval` stack.
