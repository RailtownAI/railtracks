Build your first agentic system in just a few steps.

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

def number_of_chars(text: str) -> int:
    return len(text)

def number_of_words(text: str) -> int:
    return len(text.split())

def number_of_characters(text: str, character_of_interest: str) -> int:
    return text.count(character_of_interest)

# Define the tool nodes giving your agent different capabilities
TotalNumberChars = rt.function_node(number_of_chars)
TotalNumberWords = rt.function_node(number_of_words)
CharacterCount = rt.function_node(number_of_characters)

TextAnalyzer = rt.agent_node(
    tool_nodes=[TotalNumberChars, TotalNumberWords, CharacterCount],
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message=(
        "You are a text analyzer. You will be given a text and return the number of characters, "
        "the number of words, and the number of occurrences of a specific character."
    ),
)
```

### Step 3: Run Your Application

=== "Synchronous"

    ```python
    result = rt.call_sync(
        TextAnalyzer,
        rt.llm.MessageHistory([
            rt.llm.UserMessage("Hello world! This is a test of the RailTracks framework.")
        ])
    )
    print(result)
    ```

=== "Asynchronous - Notebook"

    ```python
    result = await rt.call(
        TextAnalyzer,
        rt.llm.MessageHistory([
            rt.llm.UserMessage("Hello world! This is a test of the RailTracks framework.")
        ])
    )
    print(result)
    ```

=== "Asynchronous - Script"

    ```python
    import asyncio
    
    async def main():
        result = await rt.call(
            TextAnalyzer,
            rt.llm.MessageHistory([
                rt.llm.UserMessage("Hello world! This is a test of the RailTracks framework.")
            ])
        )
        print(result)
    
    asyncio.run(main())
    ```


### Step 4: \[Optional] Visualize the Run

```bash
railtracks init
railtracks viz
```

![RailTracks Visualization](../assets/visualizer_photo.png)

This will open a web interface showing the execution flow, node interactions, and performance metrics of your agentic system.

And just like that, you're up and running. The possibilities are endless.

---

## Contributing

We welcome contributions of all kinds! Check out our [contributing guide](https://github.com/RailtownAI/railtracks/blob/main/CONTRIBUTING.md) to get started.