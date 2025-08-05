import subprocess
import railtracks as rt



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


agent = rt.agent_node(
    tool_nodes={execute_code},
    system_message="""You are a master python programmer. To execute code, you have access to a sandboxed Python environment.
    You can execute code in it using run_in_sandbox.
    You can only see the output of the code if it is printed to stdout or stderr, so anything you want to see must be printed.
    You can install packages with code like 'import os; os.system('pip install numpy')'""",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """Create a 3x3 array of random numbers using numpy, and print the array and its mean"""
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage(user_prompt))

with rt.Session(logging_setting="VERBOSE"):
    create_sandbox_container()
    try:
        result = rt.call_sync(agent, message_history)
    finally:
        kill_sandbox()

print(result.content)
