# RailTracks Agentic Framework (RC)

## Overview

The RailTracks framework is a system designed to allow you to build simple Agentic systems that can be used to
accomplish complicated tasks. By building "agents" with specialized abilities you can accomplish much more complicated
tasks that single module could accomplish. Although the system is designed from the standpoint of LLMs being those
agents,
it is flexible and the idea of an agent could be any piece of modular functionality.

The framework is designed to support the building, testing, debugging, and deployment of
such systems. It's core principle of the system your agentic system is made up of modular components.
Each modular component has the ability to answer the upstream query or open a new downstream request
to another modular component.

## Key Features

- **Automatic Parallelism** - The backend of the RT system will automatically parallelize the execution of the modular
  components. You don't need to worry about it.
- **Streaming Capability** - By defining what you want to stream and attaching a handler you can stream updates to the
  system via a callback mechanism.
- **Error Handling** - Our predefined agents will automatically handle errors and retry requests as needed.
- **Debugging** - The system has built in logging tools that will allow high quality insights into the working of your
  system.
- **Visuals** - The system has built in visualization tools that will allow you to see the flow of your system and how
  the
  requests are being processed.
- **Definitions of Complex Flows** - RTs natural programmatic definitions of flows makes the design of complicated flows
  a breeze.
- **Configurable** - The system is designed to be configurable and extensible. You maintain full control of a variety of
  parameters that can be used to control the behavior of the system.

## Quick Start

Let's get started with building your first Agentic system. The following steps will guide you through the process of
creating a simple Agentic system using the RailTracks framework.

### Step 1: Install the Library

```bash
# Install the core library
pip install railtracks

# Install with CLI support for development and visualization
pip install railtracks[cli]
```

### Step 2: Define your Modular Components

```python
import railtracks as rt


def number_of_chars(text: str) -> int:
    """
    Counts the number of characters in the text.

    Args:
        text (str): The text to count characters in.
    """
    return len(text)


def number_of_words(text: str) -> int:
    """
    Counts the number of words in the text.

    Args:
        text (str): The text to count words in.
    """
    return len(text.split())


def number_of_characters(text: str, character_of_interest) -> int:
    """
    Counts the number of characters in the text.

    Args:
        text (str): The text to count characters in.
        character_of_interest (str): The character to count.
    """
    return len(text)


TotalNumberChars = rt.library.from_function(number_of_chars)
TotalNumberWords = rt.library.from_function(number_of_words)
CharacterCount = rt.library.from_function(number_of_characters)

TextAnalyzer = rt.library.tool_call_llm(
    connected_nodes={
        TotalNumberChars,
        TotalNumberWords,
        CharacterCount,
    },
    model=rt.llm.OpenAILLM("gpt-4o"),
    system_message=rt.llm.SystemMessage(
        "You are a text analyzer. You will be given a text and you will return the number of characters, "
        "the number of words, and the number of occurrences of a specific character in the text."
    ),
)
```

### Step 3: Run your Application

```python
import railtracks as rt

result = await rt.call(
    TextAnalyzer,
    rt.llm.MessageHistory([rt.llm.UserMessage("Hello world! This is a test of the RailTracks framework.")])
)
print(result)
```

Getting started with RT is as simple as that!. View the docs for more examples. The possibilities are truly endless.

## Contributing

See the [contributing guide](./CONTRIBUTING.md) for more information.
