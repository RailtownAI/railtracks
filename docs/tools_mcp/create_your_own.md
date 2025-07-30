# Making a Tool

Creating your own tool in RT is as simple as defining a Python function with a properly formatted docstring. Once defined, your tool can be used both directly in code and by RT agents.

The docstring serves as the tool's description when accessed by RT agents. It must follow the [Google-style docstring format](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).
(@TODO: Link to agent documentation)
(@TODO: Add programmatic injection of docstrings)

Here's an example of a tool that uses [SymPy](https://www.sympy.org/) to solve equations:

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


SolveExpressionTool = rt.library.function_node(solve_expression)
```

Alternatively, you can use a decorator to register the function directly:

```python
import railtracks as rt


@rt.function_node
def solve_expression(equation: str, solving_for: str):
    ...
```
