<div align="center">
  <div style="
    background: linear-gradient(135deg, #667eea 0%, #764ba2 25%, #f093fb 50%, #f5576c 75%, #4facfe 100%);
    padding: 60px 40px;
    border-radius: 20px;
    margin: 20px 0;
    position: relative;
    overflow: hidden;
    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
  ">
    <!-- Space stars animation -->
    <div style="
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background-image: 
        radial-gradient(2px 2px at 20px 30px, #fff, transparent),
        radial-gradient(2px 2px at 40px 70px, rgba(255,255,255,0.8), transparent),
        radial-gradient(1px 1px at 90px 40px, #fff, transparent),
        radial-gradient(1px 1px at 130px 80px, rgba(255,255,255,0.6), transparent),
        radial-gradient(2px 2px at 160px 30px, #fff, transparent);
      background-repeat: repeat;
      background-size: 200px 100px;
      animation: sparkle 3s ease-in-out infinite alternate;
      opacity: 0.6;
    "></div>
    
    <!-- Content -->
    <div style="position: relative; z-index: 2;">
      <h1 style="
        color: white;
        font-size: 4em;
        font-weight: bold;
        margin: 0 0 20px 0;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        letter-spacing: 2px;
      ">🚂 RAILTRACKS</h1>
    
      <img alt="Railtracks Logo" src="docs/assets/logo.svg" style="
        width: 200px;
        height: 200px;
        margin: 20px 0;
        filter: drop-shadow(0 10px 20px rgba(0,0,0,0.2));
      ">
      
      <h2 style="
        color: white;
        font-size: 1.8em;
        font-weight: 300;
        margin: 30px 0 0 0;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
        max-width: 800px;
        line-height: 1.4;
      ">✨ The Python framework that makes building AI agents as simple as writing functions ✨</h2>
      
      <div style="
        margin-top: 30px;
        padding: 15px 30px;
        background: rgba(255,255,255,0.1);
        border-radius: 50px;
        border: 2px solid rgba(255,255,255,0.2);
        backdrop-filter: blur(10px);
      ">
        <span style="color: white; font-weight: bold; font-size: 1.1em;">
          🎯 Zero Config • ⚡ Lightning Fast • 🔍 Fully Observable • 🐍 Pure Python
        </span>
      </div>
    </div>
  </div>
</div>

<style>
@keyframes sparkle {
  0% { transform: translateY(0px) rotate(0deg); opacity: 0.6; }
  100% { transform: translateY(-10px) rotate(5deg); opacity: 1; }
}
</style>

<p align="center">
  <a href="#-quick-start">
    <img src="https://img.shields.io/badge/Quick_Start-4285F4?style=for-the-badge&logo=rocket&logoColor=white" alt="Quick Start" />
  </a>
  <a href="https://railtownai.github.io/railtracks/">
    <img src="https://img.shields.io/badge/Documentation-00D4AA?style=for-the-badge&logo=gitbook&logoColor=white" alt="Documentation" />
  </a>
  <a href="https://github.com/RailtownAI/railtracks/tree/main/examples">
    <img src="https://img.shields.io/badge/Examples-FF6B35?style=for-the-badge&logo=github&logoColor=white" alt="Examples" />
  </a>
  <a href="https://discord.gg/h5ZcahDc">
    <img src="https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Join Discord" />
  </a>
</p>

[![PyPI version](https://img.shields.io/pypi/v/railtracks?label=release)](https://github.com/RailtownAI/railtracks/releases)
[![License](https://img.shields.io/pypi/l/railtracks)](https://opensource.org/licenses/MIT)
[![PyPI - Downloads](https://img.shields.io/pepy/dt/railtracks)](https://pypistats.org/packages/railtracks)
[![Docs](https://img.shields.io/badge/docs-latest-00BFFF.svg?logo=openbook)](https://railtownai.github.io/railtracks/)
[![GitHub stars](https://img.shields.io/github/stars/RailtownAI/railtracks.svg?style=social&label=Star)](https://github.com/RailtownAI/railtracks)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white)](https://discord.gg/h5ZcahDc)

---

## ✨ What is Railtracks?

**Railtracks** transforms how you build AI agents. While other frameworks force you into rigid workflows or complex APIs, Railtracks lets you create intelligent agents using simple Python functions and natural control flow.

```python
import railtracks as rt

# Define a tool (just a function!)
def get_weather(location: str) -> str:
    return f"It's sunny in {location}!"

# Create an agent with tools
agent = rt.agent_node(
    "Weather Assistant",
    tool_nodes={rt.function_node(get_weather)},
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You help users with weather information."
)

# Run it
result = rt.call_sync(agent, "What's the weather in Paris?")
print(result.text)  # "Based on the current data, it's sunny in Paris!"
```

**That's it.** No complex configurations, no learning proprietary syntax. Just Python.

---

## 🎯 Why Choose Railtracks?

<table>
<tr>
<td width="50%">

### 🐍 **Pure Python Experience**
- Write agents like regular Python functions
- No YAML, no DSLs, no magic strings
- Use your existing debugging tools and IDE features

### 🔧 **Tool-First Architecture**
- Any Python function becomes a tool instantly
- Seamless integration with APIs, databases, files
- Built-in support for MCP (Model Context Protocol)

</td>
<td width="50%">

### ⚡ **Automatic Intelligence**
- Smart parallelization without async/await complexity
- Built-in error handling and retries
- Automatic tool discovery and validation

### 👁️ **Transparent by Design**
- Real-time visualization of agent execution
- Complete execution history and logging
- Debug agents like you debug regular code

</td>
</tr>
</table>

---

## 🚀 Quick Start

### Installation
```bash
pip install railtracks railtracks-cli
```

### Your First Agent in 30 Seconds

```python
import railtracks as rt

# 1. Create tools (just functions with decorators!)
@rt.function_node
def count_characters(text: str, character: str) -> int:
    """Count occurrences of a character in text."""
    return text.count(character)

@rt.function_node
def word_count(text: str) -> int:
    """Count words in text."""
    return len(text.split())

# 2. Build an agent with tools
text_analyzer = rt.agent_node(
    "Text Analyzer",
    tool_nodes={count_characters, word_count},
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You analyze text using the available tools."
)

# 3. Use it to solve the classic "How many r's in strawberry?" problem
@rt.session
async def main():
    result = await rt.call(text_analyzer, "How many 'r's are in 'strawberry'?")
    print(result.text)  # "There are 3 'r's in 'strawberry'!"

# Run it
import asyncio
asyncio.run(main())
```

### Visualize Your Agent
```bash
railtracks init  # Setup visualization (one-time)
railtracks viz   # See your agent in action
```

<p align="center">
  <img src="docs/assets/visualizer_photo.png" alt="Railtracks Visualizer" width="80%">
</p>

---

## 💡 Real-World Examples

### 📊 Multi-Agent Research System
```python
# Research coordinator that uses specialized agents
researcher = rt.agent_node("Researcher", tool_nodes={web_search, summarize})
analyst = rt.agent_node("Analyst", tool_nodes={analyze_data, create_charts})
writer = rt.agent_node("Writer", tool_nodes={draft_report, format_document})

coordinator = rt.agent_node(
    "Research Coordinator",
    tool_nodes={researcher, analyst, writer},  # Agents as tools!
    system_message="Coordinate research tasks between specialists."
)
```

### 🔄 Complex Workflows Made Simple
```python
# Customer service system with context sharing
def handle_customer_request(query: str):
    with rt.Session() as session:
        # Technical support first
        technical_result = await rt.call(technical_agent, query)
        
        # Share context with billing if needed
        if "billing" in technical_result.text.lower():
            session.context["technical_notes"] = technical_result.text
            billing_result = await rt.call(billing_agent, query)
            return billing_result
        
        return technical_result
```

---

## 🌟 What Makes Railtracks Special?

**Railtracks** is a lightweight agentic LLM framework for building modular, multi-LLM workflows. Unlike other frameworks like **LangGraph** and **Google ADK**, Railtracks focuses on simplicity and developer experience.

| Feature | Railtracks | LangGraph | Google ADK |
|---------|------------|-----------|------------|
| **Python-first, no DSL** | ✅ Yes | ❌ No | ✅ Yes |
| **Built-in visualization** | ✅ Yes | ✅ Yes | ⚠️ Limited |
| **Zero setup overhead** | ✅ Yes | ✅ Yes | ❌ No |
| **LLM-agnostic** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Pure Python functions** | ✅ Yes | ❌ Complex graphs | ⚠️ Mixed |
| **Automatic optimization** | ✅ Yes | ⚠️ Manual | ⚠️ Manual |

---

## 🛠️ Powerful Features

### **🔗 Universal LLM Support**
Works with OpenAI, Anthropic, Google, local models, and more:
```python
# Switch providers effortlessly
openai_agent = rt.agent_node("Assistant", llm_model=rt.llm.OpenAILLM("gpt-4o"))
claude_agent = rt.agent_node("Assistant", llm_model=rt.llm.AnthropicLLM("claude-3-5-sonnet"))
local_agent = rt.agent_node("Assistant", llm_model=rt.llm.OllamaLLM("llama3"))
```

### **📦 Rich Tool Ecosystem** 
- **Functions**: Any Python function becomes a tool
- **MCP Integration**: Use Model Context Protocol tools
- **Agent Tools**: Use agents as tools in other agents
- **Structured Outputs**: Type-safe responses with Pydantic

### **🔍 Built-in Observability**
- Real-time execution graphs
- Performance metrics
- Error tracking and debugging
- Local visualization (no signup required!)

---

## 📚 Learn More

| Resource | Description |
|----------|-------------|
| [📖 **Documentation**](https://railtownai.github.io/railtracks/) | Complete guides and API reference |
| [🎯 **Quickstart Tutorial**](https://railtownai.github.io/railtracks/quickstart/quickstart/) | Get up and running in 5 minutes |
| [💼 **Example Gallery**](https://github.com/RailtownAI/railtracks/tree/main/examples) | Real-world agent implementations |
| [💬 **Discord Community**](https://discord.gg/h5ZcahDc) | Get help and share your creations |
| [🤝 **Contributing Guide**](./CONTRIBUTING.md) | Help make Railtracks better |

---

## 🚀 Ready to Build?

```bash
pip install railtracks railtracks-cli
```

**Join thousands of developers building the future with AI agents.** 

⭐ **Star us on GitHub** if you find Railtracks useful!

---

<p align="center">
  <strong>From simple chatbots to complex multi-agent systems—Railtracks scales with your ambitions.</strong>
</p>