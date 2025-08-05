# 🔧 Agents as Tools

In Railtracks, you can use any `Agent Node` as a tool that other agents can have access to. This allows you to create complex agents that can be composed of smaller, reusable components. 

!!! info "What are Nodes?"
    Nodes are the building blocks of Railtracks. They are responsible for executing a single task and returning a result. Read more about Nodes [here](../../system_internals/node.md).

!!! info "How to build an Agent?"
    Read more about how to build an agent [here](../../tutorials/byfa.md).


## ⚙️ Initializing an Agent that can be used as a Tool

### 1. Terminal Agent

Let's start with a simple agent that can be used as a tool:

```python
import railtracks as rt
from railtracks.nodes.manifest import ToolManifest
from railtracks.llm import Parameter

summary_agentic_tool_info = ToolManifest(
    description="You are a helpful tool that summarizes long texts.",
    parameters=[
        Parameter(name="text", description="The text to summarize.", type="str"),
    ],
)

summary_agent = rt.agent_node(
    pretty_name="Summary Agent",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful tool that summarizes long texts.",
    manifest=summary_agentic_tool_info,  # these are the specs about how this agent will be used as a tool
)
```

This agent can now be used as a tool in other agents:

```python
import railtracks as rt

@rt.function_node
def book_hotel(city: str, country: str):
    pass

@rt.function_node
def book_flight(origin: str, destination: str):
    pass

travel_agent = rt.agent_node(
    pretty_name="Travel Agent",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful travel agent."
    tool_nodes=[summary_agent, book_hotel, book_flight],  # the agent has access to these tools (summary_agent is an agent that can be used as a tool)
)
```

### 2. Tool Calling Agent

Let's create an agent that can call tools and give it a ToolManifest, so that it can be used as a tool:

```python
import railtracks as rt

# ============= START Agent 1 ==============
""" This is a ToolCallAgent that is reusable (as a tool) in other agents. """
@rt.function_node
def book_hotel(city: str, country: str):
    pass

@rt.function_node
def book_flight(origin: str, destination: str):
    pass

ticket_booker_tool_info = ToolManifest(
    description="You are a helpful travel agent.",
    parameters=[
        Parameter(name="origin_city", description="The origin city.", type="str"),
        Parameter(name="origin_country", description="The country of origin.", type="str"),
        Parameter(name="destination_city", description="The destination city.", type="str"),
        Parameter(name="destination_country", description="The country of destination.", type="str"),
    ],
)
ticker_booker = rt.agent_node(
    pretty_name="Ticket Booker",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful travel agent that can book tickets."
    tool_nodes=[book_hotel, book_flight],
    manifest=travel_agentic_tool_info,  # these are the specs about how this agent will be used as a tool
)
# ============= END Agent 1 ==============
```
!!! See also "MCP"
    [What is MCP?](../mcp/index.md)

Let's create a notion agent using the Notion MCP. <br>
Find a detailed example of how to use the Notion MCP in the [Notion Integration](../guides/notion.md) page. <br>
Once we have the notion tools from the MCP, we can use them in our agent along with a `ToolManisfest` to describe the tool:

```python
# ============= START Agent 2 ==============
""" This is a NotionAgent that is reusable (as a tool) in other agents. """
tools = server.tools    # from the Notion integration Tutorial (See link above)
notion_agent = ... 

# ============= END Agent 2 ==============
```
Finally, we can use the agents in our main agent:

```python
import railtracks as rt

travel_agent = rt.agent_node(
    pretty_name="Travel Agent",
    tool_nodes=[ticker_booker, notion_agent],  # the agent has access to these tools
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful travel agent."
)

```

## 📚 Related

Want to go further with tools in Railtracks?

* [🛠️ What *are* tools?](../index.md) <br>
  Learn how tools fit into the bigger picture of Railtracks and agent orchestration.

* [🔧 How to build your first agent](../../tutorials/byfa.md) <br>
  Follow along with a tutorial to build your first agent.

* [🤖 Using Agents as Tools](./agents_as_tools.md) <br>
  Discover how you can turn entire agents into callable tools inside other agents.

* [🧠 Advanced Tooling](./advanced_usages.md) <br>
  Explore dynamic tool loading, runtime validation, and other advanced patterns.
