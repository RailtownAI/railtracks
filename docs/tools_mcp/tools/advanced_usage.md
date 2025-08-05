# 🧠 Advanced Tooling

This page covers advanced patterns and techniques for working with tools in Railtracks, including tool behaviour encapsulation, conditional tool loading and complex agent compositions.

## 🔧 Tool Calling Agents as Tools

One powerful pattern is creating agents that can call multiple tools and then making those agents available as tools themselves. This creates a hierarchical structure where complex behaviors can be encapsulated and reused.


Let's create a math calculator agent that has access to basic math operations and can be reused as a tool:

```python
import railtracks as rt
from railtracks.nodes.manifest import ToolManifest
from railtracks.llm import Parameter

# Define basic math operation tools
@rt.function_node
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b

@rt.function_node
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b

@rt.function_node
def divide(a: float, b: float) -> float:
    """Divide two numbers."""
    if b == 0:
        return "Error: Cannot divide by zero"
    return a / b

# Create the tool manifest for the calculator
calculator_manifest = ToolManifest(
    description="A calculator agent that can perform mathematical calculations and solve math problems.",
    parameters=[
        Parameter(name="math_problem", description="The mathematical problem or calculation to solve.", type="str"),
    ],
)

# Create the calculator agent
calculator_agent = rt.agent_node(
    pretty_name="Calculator Agent",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful calculator. Solve math problems step by step using the available math operations.",
    tool_nodes=[add, multiply, divide],
    manifest=calculator_manifest,  # This makes the agent usable as a tool
)
```

**I. Invoking the Agent independently:**

This calculator can be invoked independently:

```python
# Invoke the calculator agent
result = rt.call_sync(calculator_agent, "What is 3 + 4?")
print(result.content)
```

**II. Using the Agent as a Tool:**

This calculator can be used as a tool in other agents:
```python
import railtracks as rt

@rt.function_node
def get_price_data(item: str) -> dict:
    """Get pricing data for an item."""
    # Mock pricing data
    prices = {
        "laptop": {"price": 999.99, "tax_rate": 0.08},
        "phone": {"price": 699.99, "tax_rate": 0.08},
        "tablet": {"price": 449.99, "tax_rate": 0.08}
    }
    return prices.get(item, {"price": 0, "tax_rate": 0})

# Create a shopping assistant that uses the calculator agent
shopping_assistant = rt.agent_node(
    pretty_name="Shopping Assistant",
    tool_nodes=[get_price_data, calculator_agent],  # Use the calculator agent as a tool
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a shopping assistant. Help users with pricing calculations including taxes, discounts, and totals."
)

# Demonstrate the agents working together
response = rt.call_sync(
    shopping_assistant,
    "I want to buy 3 laptops. Can you calculate the total cost including tax?"
)
print(response.content)
```

In this example: <br>
1. The **calculator agent** encapsulates math operations and can solve complex calculations <br>
2. The **shopping assistant** uses both the price lookup function and the calculator agent <br>
3. When asked about laptop costs, it fetches the price data and delegates the math to the calculator agent <br>

## 🔄 Conditional Tool Loading

For more advanced use cases, you might want to load tools dynamically based on runtime conditions or user preferences.

```python
import railtracks as rt
from typing import List, Any

def create_agent_with_conditional_tools(user_permissions: List[str]) -> rt.Node:
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

We can create sophisticated agent hierarchies where specialized agents handle specific domains.


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
Now we can create the specialized agents. <br>
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