# <strong><span style="color:#4967EF">R</span>ailtracks</strong>

The Python framework that makes building AI agents as simple as writing functions.

[![PyPI version](https://img.shields.io/pypi/v/railtracks)](https://github.com/RailtownAI/railtracks/releases)
[![Python Versions](https://img.shields.io/pypi/pyversions/railtracks?logo=python&)](https://pypi.org/project/railtracks/)
[![License](https://img.shields.io/pypi/l/railtracks)](https://opensource.org/licenses/MIT)
[![PyPI - Downloads](https://img.shields.io/pepy/dt/railtracks)](https://pypistats.org/packages/railtracks)

## Quick Start

```bash
pip install railtracks railtracks-cli
```

```python
import railtracks as rt

# Define a tool (just a function!)
@rt.function_node
def count_chars(text: str, char: str) -> int:
    return text.count(char)

# Create an agent
agent = rt.agent_node(
    "Text Analyzer", 
    tool_nodes={count_chars},
    llm_model=rt.llm.OpenAILLM("gpt-4o")
)

# Use it
result = rt.call_sync(agent, "How many 'r's in 'strawberry'?")
print(result.text)  # "There are 3 'r's in 'strawberry'!"
```

## Links

- **[📚 Documentation](https://railtownai.github.io/railtracks/)** - Complete guides and API reference
- **[💡 Examples](https://github.com/RailtownAI/railtracks/tree/main/examples)** - Real-world implementations  
- **[💬 Discord](https://discord.gg/h5ZcahDc)** - Community support
- **[🏠 Main Repository](https://github.com/RailtownAI/railtracks)** - Full project details