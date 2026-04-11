Allowing your agents to use your `python` functions as tools for your agents is quite straight forward. You can choose one of the following ways:
!!! warning "Docstrings"
    Your Python functions need to contain **_typehints_** for parameters and **_docstrings_** formatted in [Google-style docstrings](https://google.github.io/styleguide/pyguide.html#:~:text=one%2Dline%20docstring.-,Args%3A,-List%20each%20parameter) as that is what Railtracks automatically parses to inform your LLM about the capability of the tool
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

