Allowing your agents to use your `python` functions as tools for your agents is quite straight forward. You can choose one of the following ways:
!!! warning "Docstrings"
    Your Python functions need to contain **_typehints_** for parameters and **_docstrings_** as that is what Railtracks automatically parses to inform your LLM about the capability of the tool. Parameter descriptions can be written as [Google-style](https://google.github.io/styleguide/pyguide.html#:~:text=one%2Dline%20docstring.-,Args%3A,-List%20each%20parameter), [NumPy-style](https://numpydoc.readthedocs.io/en/latest/format.html), or [reST/Sphinx-style](https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html#field-lists) docstrings. Typehints always belong on the function signature itself, whatever style you pick
=== "Globally"
    ```python
    import railtracks as rt

    @rt.function_node # (1)!
    def tool_name(arg1: arg1_type, arg2: arg2_type)->return_type:
        """
        Information on what this tool does

        Args:
            arg1: what this arg is
            arg2: what this arg is

        Returns:
            information about return type
        """
        ...
    
    Agent = rt.agent_node(
        ...
        tool_nodes=[rt.function_node(some_tool)]
    )
    ```

    1. Simply add the `railtracks.function_node` decorator before the definition of your function. This transforms your function into a node type usable upon passing to any agent.

=== "Agent Specific"

    ```python
    import railtracks as rt
    from your_tool_module import some_tool

    Agent = rt.agent_node(
        ...
        tool_nodes=[rt.function_node(some_tool)]
    )
    ```

!!! warning "Tool names must be unique"
    Two *different* tools cannot share a name — the model would have no way to address them apart

    ```python
    square = rt.function_node(functools.partial(power, exp=2), name="square")
    cube = rt.function_node(functools.partial(power, exp=3), name="cube")
    ```

## Supported docstring styles

The same tool written in each of the three supported styles. All three produce identical parameter descriptions for the LLM.

=== "Google"

    ```python
    @rt.function_node
    def power(base: float, exp: float) -> float:
        """
        Raise base to the power of exp.

        Args:
            base: The number to raise.
            exp: The exponent applied to base.

        Returns:
            base raised to exp.
        """
        return base**exp
    ```

=== "NumPy"

    ```python
    @rt.function_node
    def power(base: float, exp: float) -> float:
        """
        Raise base to the power of exp.

        Parameters
        ----------
        base : float
            The number to raise.
        exp : float
            The exponent applied to base.

        Returns
        -------
        float
            base raised to exp.
        """
        return base**exp
    ```

=== "reST/Sphinx"

    ```python
    @rt.function_node
    def power(base: float, exp: float) -> float:
        """
        Raise base to the power of exp.

        :param base: The number to raise.
        :param exp: The exponent applied to base.
        :return: base raised to exp.
        """
        return base**exp
    ```

## Inspecting an agent's tools

`tool_nodes()` returns the tools avaliable to the agent, and `tool_info()` returns the tool schema that the LLM sees. 

```python
Agent = rt.agent_node("agent", llm=..., tool_nodes=[fn_a, fn_b])

Agent.tool_nodes()                            # -> [FnANode, FnBNode]
[t.tool_info() for t in Agent.tool_nodes()]   # the Tool schemas the LLM sees
```