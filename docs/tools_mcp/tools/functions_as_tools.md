# 🔧 Functions as Tools

In Railtracks, you can turn any Python function into a tool that agents can call—no special boilerplate needed. The key is to provide a [**Google-style docstring**](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html), which acts as the tool's description and schema.  

!!! info "Function Nodes"
    `rt.function_node` is a convenience function that wraps a function into a Railtrack node. Read more about this [DynamicFunctionNode](../../system_internals/node.md#dynamicfunctionnode).


## ⚙️ Creating a Function Tool

### 1. Using an RT Function
Let's start with a simple function that takes two arguments and returns their sum:

```python
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
```

To turn this function into a tool, we need to provide a docstring that describes the function's parameters. Then we can pass the function to `rt.function_node` to create a tool:

```python
import railtracks as rt

add = rt.function_node(add)
```

### 2. Using a decorator
Let's make another tool that we can use in our agent, this time using the `@rt.function_node` decorator:

```python
from sympy import solve, sympify
import railtracks as rt

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
```

## 🔮 Using the tools

Now that we have our tool, we can use it in our agent:

```python
import railtracks as rt

# Create an agent with tool access
MathAgent = rt.agent_node(
                pretty_name="MathAgent",
                tool_nodes=[
                  solve_expression, 
                  AddTool,
                ],    # the agent has access to these tools
                llm_model = rt.llm.OpenAILLM("gpt-4o"),
            )

# run the agent
result = rt.call_sync(MathAgent, "What is 3 + 4?")
```

## 📚 Related

Want to go further with tools in Railtracks?

* [🛠️ What *are* tools?](../index.md) <br>
  Learn how tools fit into the bigger picture of Railtracks and agent orchestration.

* [🤖 How to build your first agent](../../tutorials/byfa.md) <br>
  Follow along with a tutorial to build your first agent.

* [🔧 Agents as Tools](./agents_as_tools.md) <br>
  Discover how you can turn entire agents into callable tools inside other agents.

* [🧠 Advanced Tooling](./advanced_usages.md) <br>
  Explore dynamic tool loading, runtime validation, and other advanced patterns.
