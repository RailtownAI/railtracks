# 🔧 Agents as Tools

In Railtracks, you can use any `Agent Node` as a tool that other agents can have access to. This allows you to create complex agents that can be composed of smaller, reusable components. 

!!! info "What are Nodes?"
    Nodes are the building blocks of Railtracks. They are responsible for executing a single task and returning a result. Read more about Nodes [here](../../system_internals/node.md).

!!! info "How to build an Agent?"
    Read more about how to build an agent [here](../../tutorials/byfa.md).

## 📋 Understanding ToolManifest

Before diving into examples, it's important to understand what a `ToolManifest` is and why it's essential when creating agents that can be used as tools.

A `ToolManifest` is a specification that describes how an agent should be used when called as a tool by other agents. It defines:

- **Description**: What the tool does and how it should be used
- **Parameters**: What inputs the tool expects, including their names, types, and descriptions

```python
class ToolManifest:
    """
    Creates a manifest for a tool, which includes its description and parameters.

    Args:
        description (str): A description of the tool.
        parameters (Iterable[Parameter] | None): An iterable of parameters for the tool. If None, there are no parameters.
    """
```

The `ToolManifest` acts as a contract that tells other agents exactly how to interact with your agent when using it as a tool. Without it, other agents wouldn't know what parameters to pass or what to expect from your agent.

## ⚙️ Using Agents as Tools

### 🍞 Basic Example: Research Assistant

Let's create a research assistant that combines a function tool (for fetching articles) with an agent tool (for summarizing them):

```python
import railtracks as rt
from railtracks.nodes.manifest import ToolManifest
from railtracks.llm import Parameter

# First, create a function tool that fetches articles
@rt.function_node
def fetch_article(url: str) -> str:
    """Fetch the content of an article from a URL."""
    # In a real implementation, this would fetch and parse the article
    return "Mock response for fetch_article"

# Next, create an agent tool for summarizing content
summary_agent_manifest = ToolManifest(
    description="A specialized agent that creates concise summaries of long texts.",
    parameters=[
        Parameter(name="text", description="The text content to summarize.", type="str"),
        Parameter(name="length", description="Desired summary length: 'short', 'medium', or 'long'.", type="str"),
    ],
)

summary_agent = rt.agent_node(
    pretty_name="Summary Agent",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are an expert at creating clear, concise summaries. Always preserve the key points while making the content accessible.",
    manifest=summary_agent_manifest,    # This makes the agent usable as a tool
)

# Now create the main research assistant that uses both tools
research_assistant = rt.agent_node(
    pretty_name="Research Assistant",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a research assistant. When users ask about articles, fetch them and provide summaries.",
    tool_nodes=[fetch_article, summary_agent],  # Both function and agent as tools
)

# Demonstrate the tools working together
response = rt.call_sync(
    research_assistant,
    "Please fetch the article from 'https://example.com/ai-trends' and give me a short summary of the key points."
)
print(response.content)
```

In this example: <br>
1. The **function tool** (`fetch_article`) retrieves raw article content. <br>
2. The **agent tool** (`summary_agent`) intelligently processes that content into a summary. <br>
3. The main **research assistant** orchestrates both tools to complete the user's request. <br>

### 🥪 Advanced Example: Content Manager with Notion Integration

Let's create a more sophisticated example that combines data processing with Notion document creation using MCP tools:

```python
import railtracks as rt

# ================ TOOL 1 - Function as a Tool ===============
# First, create a function tool for data analysis
@rt.function_node
def analyze_sales_data(month: str, year: int) -> dict:
    """Analyze sales data for a given month and year.
    Args:
        month (str): The month to analyze.
        year (int): The year to analyze.
    """
    # In a real implementation, this would query a database
    return {"sample_data": 42}
```
!!! See also "MCP Integration"
    Find a detailed example of how to set up the Notion MCP in the [Notion Integration](../guides/notion.md) page. Learn more about MCP architecture in our [MCP Guide](../mcp/index.md).

```python
from railtracks.nodes.manifest import ToolManifest
from railtracks.llm import Parameter

# ================ TOOL 2 - Agent as a Tool ===============
# Get tools from Notion MCP (see Notion Integration guide for details)
tools = server.tools    # from the Notion integration Tutorial

# Create a Notion agent that can handle documentation tasks
notion_agent_manifest = ToolManifest(
    description="A Notion agent that can create pages, databases, and manage content in Notion workspaces.",
    parameters=[
        Parameter(name="task_description", description="Detailed description of the Notion task to perform.", type="str"),
        Parameter(name="content_data", description="Any data or content to include (as JSON string if structured data).", type="str"),
    ],
)

notion_agent = rt.agent_node(
    pretty_name="Notion Agent",
    tool_nodes=tools,  # MCP tools for Notion integration
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a Notion specialist who can create pages, update databases, manage content, and organize information in Notion workspaces.",
    manifest=notion_agent_manifest,
)
```
 Now we can create the main content manager that uses both tools:
```python
# Create the main content manager that orchestrates both tools
content_manager = rt.agent_node(
    pretty_name="Content Manager",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a content manager who creates business reports and documentation. You analyze data and organize it in Notion.",
    tool_nodes=[analyze_sales_data, notion_agent],
)

# Demonstrate the tools working together
response = rt.call_sync(
    content_manager,
    "Please analyze our sales data for March 2024 and create a comprehensive report in Notion. Create a new page called 'Q1 Sales Performance Review' with the analysis results, charts, and key insights organized in a professional format."
)
print(response.content)
```


In this example: <br>
1. The **function tool** (`analyze_sales_data`) processes and retrieves business data from various sources <br>
2. The **Notion agent tool** uses MCP tools to create pages, format content, add databases, insert charts, and organize information in Notion <br>
3. The **content manager** coordinates both tools to create comprehensive business documentation <br>

This pattern showcases the power of combining simple data processing functions with sophisticated MCP-enabled agents that can interact with external platforms like Notion, Slack, GitHub, and more.

## 📚 Related

Want to go further with tools in Railtracks?

* [🛠️ What *are* tools?](../index.md) <br>
  Learn how tools fit into the bigger picture of Railtracks and agent orchestration.

* [🔧 Functions as Tools](./functions_as_tools.md) <br>
  Learn how to turn Python functions into tools.

* [🤖 How to build your first agent](../../tutorials/byfa.md) <br>
  Start with the basics of agent creation.

* [🧠 Advanced Tooling](./advanced_usages.md) <br>
  Explore dynamic tool loading, runtime validation, and other advanced patterns including tool calling agents.