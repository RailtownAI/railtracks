# Making a Tool

Creating your own tool in RC is as simple as defining a Python function with a properly formatted docstring. Once defined, your tool can be used both directly in code and by RC agents.

The docstring serves as the tool's description when accessed by RC agents. It must follow the [Google-style docstring format](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).
(@TODO: Link to agent documentation)
(@TODO: Add programmatic injection of docstrings)

Here's an example of a tool that uses [SymPy](https://www.sympy.org/) to solve equations:

```python
from sympy import solve, sympify
import requestcompletion as rc

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

SolveExpressionTool = rc.library.from_function(solve_expression)
```

Alternatively, you can use a decorator to register the function directly:

```python
import requestcompletion as rc

@rc.to_node
def solve_expression(equation: str, solving_for: str):
    ...
```
