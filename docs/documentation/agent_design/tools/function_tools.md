Allowing your agents to use your `python` functions as tools for your agents is quite straight forward. You can choose one of the following ways:
!!! warning "Docstrings"
    Your Python functions need to contain **_typehints_** for parameters and **_docstrings_** formatted in [Google-style docstrings](https://google.github.io/styleguide/pyguide.html#:~:text=one%2Dline%20docstring.-,Args%3A,-List%20each%20parameter) as that is what Railtracks automatically parses to inform your LLM about the capability of the tool
=== "Globally"
    ```python
    import railtracks as rt

    @rt.function_node # (1)!
    def tool_name(arg1: arg1_type, arg2: arg2_type)->return_type:
        """
        Information on what this tool does

        Args:
            arg1: what this arg is
            arg2: what this arg is

        Returns:
            information about return type
        """
        ...
    
    Agent = rt.agent_node(
        ...
        tool_nodes=[rt.function_node(some_tool)]
    )
    ```

    1. Simply add the `railtracks.function_node` decorator before the definition of your function. This transforms your function into a node type usable upon passing to any agent.

=== "Agent Specific"

    ```python
    import railtracks as rt
    from your_tool_module import some_tool

    Agent = rt.agent_node(
        ...
        tool_nodes=[rt.function_node(some_tool)]
    )
    ```

!!! warning "Tool names must be unique"
    Two *different* tools cannot share a name — the model would have no way to address them apart

    ```python
    square = rt.function_node(functools.partial(power, exp=2), name="square")
    cube = rt.function_node(functools.partial(power, exp=3), name="cube")
    ```

## Inspecting an agent's tools

`tool_nodes()` returns the tools avaliable to the agent, and `tool_info()` returns the tool schema that the LLM sees. 

```python
Agent = rt.agent_node("agent", llm=..., tool_nodes=[fn_a, fn_b])

Agent.tool_nodes()                            # -> [FnANode, FnBNode]
[t.tool_info() for t in Agent.tool_nodes()]   # the Tool schemas the LLM sees
```
## Supported type hints

Railtracks derives the tool's JSON schema from your function signature. The following
annotations are understood:

| Annotation | Schema the model sees |
|---|---|
| `str`, `int`, `float`, `bool` | `{"type": "string"}`, `"integer"`, `"number"`, `"boolean"` |
| `Literal["a", "b"]` | `{"type": "string", "enum": ["a", "b"]}` |
| `List[str]`, `list[float]` | `{"type": "array", "items": {...}}` |
| `Optional[X]`, `X \| None` | the schema for `X`, marked not required |
| `X \| Y` | `{"anyOf": [...]}` |
| A `pydantic.BaseModel` | `{"type": "object", "properties": {...}}` |

Anything Railtracks cannot recognise falls back to `{"type": "object"}`.

## Overriding the inferred schema

Pass a `ToolManifest` when you want to declare the schema yourself instead of relying
on inference:

```python
import railtracks as rt
from railtracks.llm import Parameter

node = rt.function_node(
    search_files,
    manifest=rt.ToolManifest(
        "Search files by regex.",
        [
            Parameter(
                "pattern",
                param_type="string",
                description="Regex to search for.",
                required=True,
            )
        ],
    ),
)
```

The manifest is the schema sent to the model. Railtracks still
checks that the parameter *names* line up with the function signature and raises if they
do not. A type that disagrees with the signature only warns.
