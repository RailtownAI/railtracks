# Using Shell as a tool with RequestCompletion

To allow for usage of shell as a tool, we can create a simple tool using `from_fuction`. The function could be modified to suit your needs, such as adding error handling or specific command restrictions. Below is a basic example of how to create a shell command execution tool using `subprocess` in Python.

```python
--8<-- "docs/scripts/tools_mcp_guides.py:bash_tool"
```

At this point, the tool can be used the same as any other RT tool. See the following code as a simple example.

```python
--8<-- "docs/scripts/tools_mcp_guides.py:bash_call"
```
