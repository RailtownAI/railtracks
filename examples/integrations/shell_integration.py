import subprocess
import platform
import railtracks as rt


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


bash_tool = rt.function_node(run_shell)

##################################################################
# Example using the tools with an agent

agent = rt.agent_node(
    tool_nodes={bash_tool},
    system_message=f"You are a useful helper that can run local shell commands. "
                   f"You are on a {platform.system()} machine. Use appropriate shell commands to answer the user's questions.",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
)

user_prompt = """What directories are in the current directory?"""
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage(user_prompt))

with rt.Session(logging_setting="VERBOSE"):
    result = rt.call_sync(agent, message_history)

print(result.content)
