# 🧠 Advanced Tooling

This page covers advanced patterns and techniques for working with tools in Railtracks, including dynamic tool loading and complex agent compositions.

## 🔧 Tool Calling Agents as Tools

One powerful pattern is creating agents that can call multiple tools and then making those agents available as tools themselves. This creates a hierarchical structure where complex behaviors can be encapsulated and reused.

### Creating a Reusable Tool Calling Agent

Let's create a ticket booking agent that can handle both flights and hotels, and make it available as a tool:

```python
import railtracks as rt
from railtracks.nodes.manifest import ToolManifest
from railtracks.llm import Parameter

# Define the individual tools
@rt.function_node
def book_hotel(city: str, country: str):
    """Book a hotel in the specified city and country."""
    # Hotel booking logic here
    return f"Hotel booked in {city}, {country}"

@rt.function_node
def book_flight(origin: str, destination: str):
    """Book a flight from origin to destination."""
    # Flight booking logic here
    return f"Flight booked from {origin} to {destination}"

# Create the tool manifest for the ticket booker
ticket_booker_tool_info = ToolManifest(
    description="A comprehensive travel booking agent that can book flights and hotels.",
    parameters=[
        Parameter(name="origin_city", description="The origin city.", type="str"),
        Parameter(name="origin_country", description="The country of origin.", type="str"),
        Parameter(name="destination_city", description="The destination city.", type="str"),
        Parameter(name="destination_country", description="The country of destination.", type="str"),
    ],
    
)

# Create the ticket booker agent
ticket_booker = rt.agent_node(
    pretty_name="Ticket Booker",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful travel agent that can book both flights and hotels. When given travel details, book both the flight and accommodation.",
    tool_nodes=[book_hotel, book_flight],
    manifest=ticket_booker_tool_info,  # This makes the agent usable as a tool
)
```

### Using the Tool Calling Agent

Now this complex agent can be used as a single tool in other agents:

```python
import railtracks as rt

# Create a high-level travel assistant
travel_assistant = rt.agent_node(
    pretty_name="Travel Assistant",
    tool_nodes=[ticket_booker],  # Use the complex agent as a simple tool
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a travel assistant that helps users plan and book their trips."
)

# Use the travel assistant
response = rt.call_sync(
    travel_assistant,
    "I need to travel from London, UK to Paris, France next week. Can you help me book everything?"
)
print(response.content)
```

## 🔄 Conditional Tool Loading

For more advanced use cases, you might want to load tools dynamically based on runtime conditions or user preferences.

```python
import railtracks as rt
from typing import List, Any

def create_agent_with_conditional_tools(user_permissions: List[str]) -> rt.AgentNode:
    """Create an agent with tools based on user permissions."""
    
    available_tools = []
    
    # Base tools available to everyone
    @rt.function_node
    def get_weather(location: str):
        return f"Weather in {location}: Sunny, 22°C"
    
    available_tools.append(get_weather)
    
    # Admin-only tools
    if "admin" in user_permissions:
        @rt.function_node
        def delete_user(user_id: str):
            return f"User {user_id} deleted"
        
        available_tools.append(delete_user)
    
    # Premium user tools
    if "premium" in user_permissions:
        @rt.function_node
        def advanced_analytics():
            return "Advanced analytics data..."
        
        available_tools.append(advanced_analytics)
    
    return rt.agent_node(
        pretty_name="Dynamic Agent",
        llm_model=rt.llm.OpenAILLM("gpt-4o"),
        system_message="You are a helpful assistant with access to various tools based on user permissions.",
        tool_nodes=available_tools
    )

# Usage
admin_agent = create_agent_with_conditional_tools(["admin", "premium"])
basic_agent = create_agent_with_conditional_tools([])
```

## 🏗️ Complex Agent Hierarchies

Create sophisticated agent hierarchies where specialized agents handle specific domains.


```python
import railtracks as rt
from railtracks.nodes.manifest import ToolManifest
from railtracks.llm import Parameter

# Domain-specific agents
email_agent_manifest = ToolManifest(
    description="Handles all email-related tasks",
    parameters=[
        Parameter(name="action", description="The email action to perform", type="str"),
        Parameter(name="details", description="Details for the email action", type="str"),
    ],
)

calendar_agent_manifest = ToolManifest(
    description="Manages calendar and scheduling tasks",
    parameters=[
        Parameter(name="action", description="The calendar action to perform", type="str"),
        Parameter(name="details", description="Details for the calendar action", type="str"),
    ],
)
```
Now we can create the specialized agents, that have access to specific tools. <br>
In this case we are assuming we have multiple tools defined:

```python
# Create specialized agents
email_agent = rt.agent_node(
    pretty_name="Email Agent",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You specialize in email management and communication tasks.",
    tool_nodes=[send_email, ...],  # Assume send_email is defined
    manifest=email_agent_manifest
)

calendar_agent = rt.agent_node(
    pretty_name="Calendar Agent",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You specialize in calendar and scheduling tasks.",
    tool_nodes=[...],  # Add calendar tools here
    manifest=calendar_agent_manifest
)

```

Now we can create the coordinator agent that combines these multi-domain agents:

```python
# Master coordinator agent
coordinator_agent = rt.agent_node(
    pretty_name="Personal Assistant",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a personal assistant that coordinates with specialized agents to help users.",
    tool_nodes=[email_agent, calendar_agent]
)
```

## 📚 Related

* [🔧 Agents as Tools](./agents_as_tools.md) <br>
  Learn the basics of using agents as tools.

* [🔧 Functions as Tools](./functions_as_tools.md) <br>
  Learn how to turn Python functions into tools.

* [🛠️ What *are* tools?](../index.md) <br>
  Understand the fundamental concepts of tools in Railtracks.

* [🤖 How to build your first agent](../../tutorials/byfa.md) <br>
  Start with the basics of agent creation.