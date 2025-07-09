import subprocess
import requestcompletion as rc
from requestcompletion.nodes.library import tool_call_llm


def container_exists(session_id: str) -> bool:
    result = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name=sandbox_{session_id}"],
        stdout=subprocess.PIPE
    )
    return bool(result.stdout.strip())


def create_sandbox_container(session_id: str):
    subprocess.run([
        "docker", "run", "-dit", "--rm",
        "--name", f"sandbox_{session_id}",
        # "--network", "none",
        "--memory", "512m", "--cpus", "0.5",
        "python:3.12-slim", "python3"
    ])


def execute_code(session_id: str, code: str) -> str:
    if not container_exists(session_id):
        return (
            f"No running Python environment for session_id {session_id}.\n"
            f"Please start it using `create_sandbox_container(session_id)` before running code."
        )

    exec_result = subprocess.run([
        "docker", "exec", f"sandbox_{session_id}",
        "python3", "-c", code
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return exec_result.stdout.decode() + exec_result.stderr.decode()


def kill_sandbox(session_id: str):
    subprocess.run(["docker", "rm", "-f", f"sandbox_{session_id}"])


agent = tool_call_llm(
    connected_nodes={create_sandbox_container, execute_code, kill_sandbox},
    system_message="""You are a master python programmer. To execute code, you have access to a sandboxed Python environment.
    You can create a sandbox container, execute code in it, and then kill the container when done.
    You can install packages with code like "import os; os.system('pip install numpy')""",
    model=rc.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """Create a simple function that generates a random number. Run that function and return that number"""
message_history = rc.llm.MessageHistory()
message_history.append(rc.llm.UserMessage(user_prompt))

with rc.Runner(rc.ExecutorConfig(logging_setting="VERBOSE")) as run:
    result = run.run_sync(agent, message_history)

print(result.answer.content)
