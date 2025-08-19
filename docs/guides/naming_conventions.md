# Node Naming Conventions

RailTracks follows specific naming conventions to provide clear, consistent names for debugging and development while maintaining valid identifiers for tool calls.

## Function Nodes

When creating function nodes using `rt.function_node()`, the display name of the node automatically converts from `snake_case` to `Title Case`:

```python
import railtracks as rt

def number_of_chars(text: str) -> int:
    return len(text)

def calculate_sum(x: float, y: float) -> float:
    return x + y

# Function nodes automatically get Title Case names
CharsNode = rt.function_node(number_of_chars)
SumNode = rt.function_node(calculate_sum)

print(CharsNode.node_type.name())  # "Number Of Chars"
print(SumNode.node_type.name())    # "Calculate Sum"
```

## Custom Names

You can override the default naming by providing an explicit name:

```python
CustomNode = rt.function_node(number_of_chars, name="Character Counter")
print(CustomNode.node_type.name())  # "Character Counter"
```

## Tool Names vs Display Names

While node display names use Title Case for better readability, tool names (used for LLM tool calls) remain in snake_case to ensure valid identifiers:

```python
CharsNode = rt.function_node(number_of_chars)

# Display name (for debugging/visualization)
print(CharsNode.node_type.name())           # "Number Of Chars"

# Tool name (for LLM tool calls)  
print(CharsNode.node_type.tool_info().name) # "number_of_chars"
```

## Library Nodes

All built-in library nodes follow the Title Case convention:

- Terminal LLM nodes: `"Terminal LLM"`
- Tool Call LLM nodes: `"Tool Call LLM"`
- Structured LLM nodes: `"Structured LLM (OutputSchema)"`

## Rationale

Title Case names provide several benefits:

1. **Better debugging experience** - More readable in logs and visualizations
2. **Professional appearance** - Cleaner presentation in UI components
3. **Consistency** - Uniform naming across all RailTracks components
4. **Tool compatibility** - Maintains valid snake_case identifiers for LLM tools

This convention balances human readability with technical requirements, ensuring your agentic systems are both developer-friendly and robust.