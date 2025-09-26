# Running python code with RailTracks
This is a simple guide to running Python code with RailTracks, using a Docker container as a sandboxed environment.
Before running the code, make sure you have Docker installed and running on your machine.

```python
--8<-- "docs/scripts/tools_mcp_guides.py:sandbox_setup"
```

When running the agent, use the `create_sandbox_container` function to start the Docker container before running the agent, and the `kill_sandbox` function to stop and remove the container after you're done.
The following example shows how to use the agent to execute Python code in the sandboxed environment:

```python
--8<-- "docs/scripts/tools_mcp_guides.py:sandbox_call"
```
