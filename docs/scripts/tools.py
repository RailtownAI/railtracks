import railtracks as rt
from sympy import solve, sympify

# --8<-- [start: add]
def add(a: int, b: int) -> int:
    """
    Adds two numbers together.
    Args:
        a (int): The first number.
        b (int): The second number.

    Returns:
        int: The sum of the two numbers.
    """
    return a + b
# --8<-- [end: add]

# --8<-- [start: function_node]
AddNode = rt.function_node(add)
# --8<-- [end: function_node]

# --8<-- [start: decorator]
@rt.function_node
def solve_expression(equation: str, solving_for: str):
    """
    Solves the given equation (assumed to be equal to 0) for the specified variable.

    Args:
        equation (str): The equation to solve, written in valid Python syntax.
        solving_for (str): The variable to solve for.
    """
    # Convert the string into a symbolic expression
    eq = sympify(equation, evaluate=True)

    # Solve the equation for the given variable
    return solve(eq, solving_for)
# --8<-- [end: decorator]

# --8<-- [start: agent]
MathAgent = rt.agent_node(
                name="MathAgent",
                tool_nodes=[
                  solve_expression, 
                  AddNode,
                ],    # the agent has access to these tools
                llm_model = rt.llm.OpenAILLM("gpt-4o"),
            )

# run the agent
result = rt.call_sync(MathAgent, "What is 3 + 4?")
# --8<-- [end: agent]
