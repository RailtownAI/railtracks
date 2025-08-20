# Functions as Tools

In Railtracks, you can turn any Python function into a tool that agents can call, no special boilerplate needed. The key is to provide a [**Google-style docstring**](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html) which acts as the tool's description and schema.  

!!! info "Function Nodes"
    `rt.function_node` is a convenience function that wraps a function into a Railtrack node. Read more about this [DynamicFunctionNode](../../system_internals/node.md#dynamicfunctionnode).


## Creating a Function Tool

### 1. Using an RT Function
Let's start with a simple function that takes two arguments and returns their sum:

```python
---8<-- "docs/scripts/tools.py:add"
```

To turn this function into a tool, we need to provide a docstring that describes the function's parameters. Then we can pass the function to `rt.function_node` to create a tool:

```python
---8<-- "docs/scripts/tools.py:function_node"
```

### 2. Using a decorator
Let's make another tool that we can use in our agent, this time using the `@rt.function_node` decorator:

```python
---8<-- "docs/scripts/tools.py:decorator"
```

## Using the tools

Now that we have our tool, we can use it in our agent:

```python
---8<-- "docs/scripts/tools.py:agent"
```

## Naming Conventions

!!! info "Title Case Function Names"
    RailTracks automatically converts function names from `snake_case` to `Title Case` for better debugging and visualization while preserving `snake_case` for tool identifiers.

When creating function nodes, RailTracks automatically converts the function name:

```python
def number_of_chars(text: str) -> int:
    return len(text)

CharsNode = rt.function_node(number_of_chars)
print(CharsNode.node_type.name())           # "Number Of Chars" ✨
print(CharsNode.node_type.tool_info().name) # "number_of_chars" (for LLM tools)
```

!!! tip "Custom Names"
    You can override the default naming by providing an explicit name:
    ```python
    CustomNode = rt.function_node(number_of_chars, name="Character Counter")
    ```

## Related

Want to go further with tools in Railtracks?

* [What *are* tools?](../index.md) <br>
  Learn how tools fit into the bigger picture of Railtracks and agent orchestration.

* [How to build your first agent](../../tutorials/byfa.md) <br>
  Follow along with a tutorial to build your first agent.

* [Agents as Tools](./agents_as_tools.md) <br>
  Discover how you can turn entire agents into callable tools inside other agents.

* [Advanced Tooling](./advanced_usages.md) <br>
  Explore dynamic tool loading, runtime validation, and other advanced patterns.
