# Agents as Tools

In Railtracks, you can use any **Agent** as a tool that other agents can use. This allows you to create complex agents that can be composed of smaller, reusable components.

How to build an Agent?

Read more about how to build an agent [**Build your First Agent**](https://docs.railtracks.org/tutorials/walkthroughs/byfa/index.md).

## Understanding **`ToolManifest`**

Before diving into examples, it's important to understand what a **`ToolManifest`** is and why it's essential when creating agents that can be used as tools - it's a specification that describes how an agent should be used when called as a tool by other agents and defines:

- **`description`**: What the tool does and how it should be used
- **`parameters`**: What inputs the tool expects, including their names, types, and descriptions

**`ToolManifest`**

For complete details on **`ToolManifest`**, see the [API Reference](https://docs.railtracks.org/api_reference/railtracks.html#ToolManifest).

**`Parameter`**

For complete details on **`Parameter`**, see the [API Reference](https://docs.railtracks.org/api_reference/railtracks/llm.html#Parameter).

```python
calculator_manifest = rt.ToolManifest(
    description="A calculator agent that can perform mathematical calculations and solve math problems.",
    parameters=[
        rt.llm.Parameter(
            name="math_problem",
            description="The mathematical problem or calculation to solve.",
            param_type="string",
        ),
    ],
)
```

The **`ToolManifest`** acts as a contract that tells other agents exactly how to interact with your agent when using it as a tool. Without it, other agents wouldn't know what parameters to pass or what to expect from your agent.

### Working Example: Shopping Assistant

One powerful pattern is creating agents that can call multiple tools and then making those agents available as tools themselves. This creates a hierarchical structure where complex behaviors can be encapsulated and reused. In this example, we will create a **`ShoppingAssistant`** agent that can perform calculations and look up product prices using a calculator agent and a price lookup function.

```
graph TB
    CA[CalculatorAgent]:::agent
    CA --> add[add]:::tool
    CA --> multiply[multiply]:::tool
    CA --> divide[divide]:::tool

    SA[ShoppingAssistant]:::agent
    SA --> CA
    SA --> GPD[get_price_data]:::tool

    classDef agent fill:#60A5FA,fill-opacity:0.4
    classDef tool fill:#FBBF24,fill-opacity:0.4
```

#### Step 1: **`CalculatorAgent`**

Let's create a math calculator agent that has access to basic math operations and can be reused as a tool:

```python
CalculatorAgent = rt.agent_node(
    name="Calculator Agent",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="You are a helpful calculator. Solve math problems step by step using the available math operations.",
    tool_nodes=[add, multiply, divide],
    manifest=calculator_manifest,  # This makes the agent usable as a tool
)
```

Calculation Tools

Although these functions are simple, they demonstrate how to encapsulate functionality for an agent.

```python
@rt.function_node
def add(a: float, b: float) -> float:
    """Add two numbers together.

    Args:
        a (float): The first number to add.
        b (float): The second number to add.

    Returns:
        float: The sum of a and b.
    """
    return a + b

@rt.function_node
def multiply(a: float, b: float) -> float:
    """Multiply two numbers together.

    Args:
        a (float): The first number to multiply.
        b (float): The second number to multiply.

    Returns:
        float: The product of a and b.
    """
    return a * b

@rt.function_node
def divide(a: float, b: float) -> float:
    """Divide one number by another.

    Args:
        a (float): The dividend (number to be divided).
        b (float): The divisor (number to divide by).

    Returns:
        float: The quotient of a divided by b.

    Raises:
        ZeroDivisionError: When b is zero, returns an error message string instead.
    """
    if b == 0:
        raise ZeroDivisionError("Error: Cannot divide by zero")
    return a / b
```

#### Step 1.1 Invoking the Agent Independently

This calculator can be invoked independently:

```python
flow = rt.Flow("calculator-flow", entry_point=CalculatorAgent)
result = flow.invoke("What is 3 + 4?")
```

#### Step 1.2 Using the Agent as a Tool

This calculator can be used as a tool in other agents:

```python
ShoppingAssistant = rt.agent_node(
    name="Shopping Assistant",
    tool_nodes=[get_price_data, CalculatorAgent],  # Use the calculator agent as a tool
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message=(
        "You are a shopping assistant." 
        "Help users with pricing calculations including taxes, discounts, and totals."
        )
)
```

Pricing Tool

You might have noticed we also provided an extra tool to the agent in addition to the **`CalculatorAgent`** called **`get_price_data`**. This is a simple function that simulates looking up product prices.

```python
@rt.function_node
def get_price_data(item: str) -> dict:
    """
    Retrieves price and tax rate information for common electronic items.
    Returns default values for unknown items.

    Args:
        item (str): The name of the item to look up (e.g., "laptop", "phone", "tablet").
    """
    # Mock pricing data
    prices = {
        "laptop": {"price": 999.99, "tax_rate": 0.08},
        "phone": {"price": 699.99, "tax_rate": 0.08},
        "tablet": {"price": 449.99, "tax_rate": 0.08}
    }
    return prices.get(item, {"price": 0, "tax_rate": 0})
```

In this example:

1. The **`CalculatorAgent`** encapsulates math operations and can solve complex calculations
1. The **`ShoppingAssistant`** uses both the price lookup function and the calculator agent
1. When asked about laptop costs, it fetches the price data and delegates the math to the calculator agent

```python
shopping_flow = rt.Flow("shopping-flow", entry_point=ShoppingAssistant)
response = shopping_flow.invoke("I want to buy 3 laptops. Can you calculate the total cost including tax?")
```

Sample Output

Here is a sample out of the running the **`ShoppingAssistant`** agent for the above user query. Please note that the output may vary based on the current training date cutoff of the LLM you use.

```console
The total cost for 3 laptops, including tax, is approximately $3,239.97.
```

Congratulations! You have created an agent that can be used as a tool by other agents. This pattern allows you to build complex behaviors by composing smaller, reusable components.

## Related

Want to go further with tools in Railtracks?

- [What are tools?](https://docs.railtracks.org/tutorials/concepts/tools/index.md)\
  Learn how tools fit into the bigger picture of Railtracks and agent orchestration.
- [Functions as Tools](https://docs.railtracks.org/documentation/agent_design/tools/function_tools/index.md)\
  Learn how to turn Python functions into tools.
- [How to build your first agent](https://docs.railtracks.org/tutorials/walkthroughs/byfa/index.md)\
  Start with the basics of agent creation.
