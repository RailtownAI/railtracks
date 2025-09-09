# Custom Class Building with NodeBuilder

RailTracks' `define_agent` provides a robust foundation for configuring agent classes with predefined parameters that handle most use cases. However, when you need agents or nodes with specialized functionality beyond these standard configurations, the **NodeBuilder** class offers the flexibility to create custom implementations while maintaining the core RailTracks functionality.

## Overview

NodeBuilder enables you to:
- Inherit from existing RailTracks node classes
- Add custom class methods and attributes
- Maintain compatibility with the RailTracks ecosystem
- Create specialized agents tailored to your specific requirements

---

## Getting Started

### 1. Initialize NodeBuilder

Begin by selecting the appropriate base node class for inheritance. 
!!! Note "Common Classes"

    - **Terminal** - For endpoint nodes
    - **Structured** - For nodes with structured outputs
    - **ToolCall** - For nodes that can call tools
    - **StructuredToolCall** - For nodes combining structured outputs with tool calling

When initializing NodeBuilder, you'll specify both a `name` and `class_name`:
- **`name`**: User-friendly identifier for differentiation in multi-node scenarios
- **`class_name`**: Internal identifier used by RailTracks and Python

```python
builder = NodeBuilder[StructuredLLM[_TOutput]](
    StructuredLLM,
    name='yourAgentName',
    class_name='yourClassName',
)
```

### 2. Configure LLM Base (Optional)

For nodes that utilize Large Language Models, use the `llm_base` method to specify the system message and model:

```python
builder.llm_base(your_llm_model, your_system_message)
```

!!! Warning
    While LLM configuration is technically optional, it's highly recommended. If you are making a non-LLM node, consider using function nodes instead.

---

## Adding Functionality

NodeBuilder provides several methods to decide your node's capabilities, mirroring the functionality available in `agent_node` :

### Core Functionality Options

| Method | Purpose | Required For |
|--------|---------|--------------|
| `structured(output_schema)` | Define structured output format | Structured classes |
| `tool_callable_llm(tool_details, tool_params)` | Enable tool invocation capabilities | ToolCall classes |
| `tool_calling_llm(tool_nodes, max_tool_calls)` | Configure tool calling behavior | ToolCall classes |

```python
# Structured output
builder.structured(output_schema)

# Tool capabilities
builder.tool_callable_llm(tool_details, tool_params)
builder.tool_calling_llm(tool_nodes, max_tool_calls)
```

### Custom Attributes

Extend your node with custom methods or class variables using the `add_attribute` method:

```python
builder.add_attribute(
    attribute_name,
    is_function,
    args,
    kwargs
)
```

---

## Building Your Node

Complete the build process by calling the `build()` method:

```python
node = builder.build()
```

---

## Complete Example

```python
# Initialize the builder
builder = NodeBuilder[StructuredToolCallLLM[_TOutput]](
    StructuredToolCallLLM,
    name=name,
    class_name="EasyStructuredToolCallLLM",
    return_into=return_into,
    format_for_return=format_for_return,
    format_for_context=format_for_context,
)

# Configure LLM base
builder.llm_base(llm_model, system_message)

# Add tool functionality
builder.tool_calling_llm(set(tool_nodes), max_tool_calls)
builder.tool_callable_llm(tool_details, tool_params)

# Configure structured output
builder.structured(output_schema)

# Build the final node
node = builder.build()
```

