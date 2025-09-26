import asyncio
import railtracks as rt

# --8<-- [start: calculation_tools]
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
        return "Error: Cannot divide by zero"
    return a / b
# --8<-- [end: calculation_tools]

# --8<-- [start: manifest]
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
# --8<-- [end: manifest]

# --8<-- [start: calculation_agent]
CalculatorAgent = rt.agent_node(
    name="Calculator Agent",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful calculator. Solve math problems step by step using the available math operations.",
    tool_nodes=[add, multiply, divide],
    manifest=calculator_manifest,  # This makes the agent usable as a tool
)
# --8<-- [end: calculation_agent]

# --8<-- [start: call]
async def top_level():
    result = await rt.call(
        CalculatorAgent, 
        "What is 3 + 4?"
        )
    return result
result = asyncio.run(top_level())
# --8<-- [end: call]
print(result.content)

# --8<-- [start: pricing_tool]
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
# --8<-- [end: pricing_tool]

# --8<-- [start: shopping_agent]
ShoppingAssistant = rt.agent_node(
    name="Shopping Assistant",
    tool_nodes=[get_price_data, CalculatorAgent],  # Use the calculator agent as a tool
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message=(
        "You are a shopping assistant." 
        "Help users with pricing calculations including taxes, discounts, and totals."
        )
)
# --8<-- [end: shopping_agent]

# --8<-- [start: shop_call]
async def top_level():
    response = await rt.call(
        ShoppingAssistant,
        "I want to buy 3 laptops. Can you calculate the total cost including tax?",
    )
    return response
response = asyncio.run(top_level())
# --8<-- [end: shop_call]
print(response)
