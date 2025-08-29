# Using Shell as a tool with RequestCompletion

To allow for usage of shell as a tool, we can create a simple tool using `from_fuction`. The function could be modified to suit your needs, such as adding error handling or specific command restrictions. Below is a basic example of how to create a shell command execution tool using `subprocess` in Python.

```python
import subprocess
from railtracks.nodes.library import function_node


def run_shell(command: str) -> str:
    """Run a bash command and return its output or error."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"Error: {result.stderr.strip()}"
    except Exception as e:
        return f"Exception: {str(e)}"


bash_tool = function_node(run_shell)
```

At this point, the tool can be used the same as any other RT tool. See the following code as a simple example.

```python
import platform

import railtracks as rt

agent = rt.agent_node(
    tool_nodes={bash_tool},
    system_message=f"You are a useful helper that can run local shell commands. "
                   f"You are on a {platform.system()} machine. Use appropriate shell commands to answer the user's questions.",
    llm=rt.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """What directories are in the current directory?"""
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage(user_prompt))

with rt.Session(logging_setting="VERBOSE"):
    result = rt.call_sync(agent, message_history)

print(result.answer.content)
```
