# Running python code with RailTracks
This is a simple guide to running Python code with RailTracks, using a Docker container as a sandboxed environment.
Before running the code, make sure you have Docker installed and running on your machine.

```python
import subprocess
import railtracks as rt
from railtracks.nodes.library import tool_call_llm


def create_sandbox_container():
    subprocess.run([
        "docker", "run", "-dit", "--rm",
        "--name", "sandbox_chatbot_session",
        "--memory", "512m", "--cpus", "0.5",
        "python:3.12-slim", "python3"
    ])


def kill_sandbox():
    subprocess.run(["docker", "rm", "-f", "sandbox_chatbot_session"])


def execute_code(code: str) -> str:
    exec_result = subprocess.run([
        "docker", "exec", "sandbox_chatbot_session",
        "python3", "-c", code
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return exec_result.stdout.decode() + exec_result.stderr.decode()


agent = tool_call_llm(
    connected_nodes={execute_code},
    system_message="""You are a master python programmer. To execute code, you have access to a sandboxed Python environment.
    You can execute code in it using run_in_sandbox.
    You can only see the output of the code if it is printed to stdout or stderr, so anything you want to see must be printed.
    You can install packages with code like 'import os; os.system('pip install numpy')'""",
    model=rt.llm.OpenAILLM("gpt-4o"),
)
```

When running the agent, use the `create_sandbox_container` function to start the Docker container before running the agent, and the `kill_sandbox` function to stop and remove the container after you're done.
The following example shows how to use the agent to execute Python code in the sandboxed environment:

```python
user_prompt = """Create a 3x3 array of random numbers using numpy, and print the array and its mean"""
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage(user_prompt))

with rt.Runner(rt.ExecutorConfig(logging_setting="VERBOSE")) as run:
    create_sandbox_container()
    try:
        result = run.run_sync(agent, message_history)
    finally:
        kill_sandbox()

print(result.answer.content)
```
