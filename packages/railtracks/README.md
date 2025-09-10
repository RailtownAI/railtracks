# RailTracks

![RailTracks](../../docs/assets/logo.svg)

## Quick Start

Build your first agentic system in just a few steps. Start by building an agent which solves the "how many `r`'s are in Strawberry?" problem. 

### Step 1: Install the Library

```bash
# Core library
pip install railtracks

# [Optional] CLI support for development and visualization
pip install railtracks-cli
```

### Step 2: Define Your Modular Components

```python
import railtracks as rt

# Create your tool
@rt.function_node
def number_of_characters(text: str, character_of_interest: str) -> int:
    return text.count(character_of_interest)

# Create your agent (connecting your LLM)
TextAnalyzer = rt.agent_node(
    tool_nodes={number_of_chars, num, CharacterCount},
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message=(
        "You are a text analyzer. You will be given a text and return the number of characters, "
        "the number of words, and the number of occurrences of a specific character."
    ),
)
```

### Step 3: Run Your Application

```python
@rt.session
async def main():
    result = await rt.call(
        TextAnalyzer,
        rt.llm.MessageHistory([
            rt.llm.UserMessage("Hello world! This is a test of the RailTracks framework.")
        ])
    )
    print(result)
```

### Step 4: \[Optional] Visualize the Run

```bash
railtracks init
railtracks viz
```

And just like that, you're up and running. The possibilities are endless.

---

## Contributing

We welcome contributions of all kinds! Check out our [contributing guide](../../CONTRIBUTING.md) to get started.