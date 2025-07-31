# 🔧 Exposing Functions as Tools

In Railtracks, you can turn any Python function into a tool that agents can call—no special boilerplate needed. The key is to provide a **Google-style docstring**, which acts as the tool's description and schema.

---

## 🧠 What Is a Tool?

A **tool** is simply a function that has been wrapped using `rt.function_node(...)`, making it callable by agents or orchestrated within larger flows.

!!! info "python function -> node"
    When you call `rt.function_node(...)`, you're basically creating a Dynamic Function Node, which is a specialized version of a normal node that can be called by agents.
---

## ⚙️ Creating a Function Tool

Here’s all it takes to create your own tool:

```python
from sympy import solve, sympify
import railtracks as rt

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

SolveExpressionTool = rt.function_node(solve_expression)
```