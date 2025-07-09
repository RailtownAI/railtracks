import subprocess
import platform

from requestcompletion.nodes.library.easy_usage_wrappers.tool_call_llm import tool_call_llm
import requestcompletion as rc


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


bash_tool = rc.library.from_function(run_shell)

##################################################################
# Example using the tools with an agent

agent = tool_call_llm(
    connected_nodes={bash_tool},
    system_message=f"You are a useful helper that can run local shell commands. "
                   f"You are on a {platform.system()} machine. Use appropriate shell commands to answer the user's questions.",
    model=rc.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """What directories are in the current directory?"""
message_history = rc.llm.MessageHistory()
message_history.append(rc.llm.UserMessage(user_prompt))

with rc.Runner(rc.ExecutorConfig(logging_setting="VERBOSE")) as run:
    result = run.run_sync(agent, message_history)

print(result.answer.content)
