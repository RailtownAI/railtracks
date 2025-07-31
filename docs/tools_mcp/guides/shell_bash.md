# Shell Integration

Enable your Railtracks agents to execute shell commands and interact with your local system, automating tasks and retrieving system information.

**Version:** 0.0.1

---

## 1. What You Can Do

The Shell integration enables your Railtracks agents to:

- **System Information**: Get details about your system, processes, and environment
- **File Operations**: Navigate directories, list files, and manage file systems
- **Development Tasks**: Run build commands, tests, and development workflows
- **System Administration**: Monitor system resources and perform maintenance tasks
- **Automation**: Execute scripts and automate repetitive command-line tasks

## 2. Quick Start

Get started with shell integration in just a few steps:

### Step 1: Create a shell command tool

```python
import subprocess
import platform
import railtracks as rt
from railtracks.nodes.library.easy_usage_wrappers.tool_call_llm import tool_call_llm

def run_shell(command: str) -> str:
    """Run a shell command and return its output or error."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"Error: {result.stderr.strip()}"
    except Exception as e:
        return f"Exception: {str(e)}"

# Create the tool from your function
bash_tool = rt.library.from_function(run_shell)
```

### Step 2: Create an agent with shell capabilities

```python
agent = tool_call_llm(
    connected_nodes={bash_tool},
    system_message=f"""You are a helpful system administrator assistant that can run shell commands. 
    You are on a {platform.system()} machine. Use appropriate shell commands to answer questions 
    and help with system tasks. Always be careful with commands that modify the system.""",
    model=rt.llm.OpenAILLM("gpt-4o"),
)
```

### Step 3: Start using your agent

```python
# Ask your agent to perform system tasks
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage("What directories are in the current directory?"))

with rt.Runner(rt.ExecutorConfig(logging_setting="VERBOSE")) as run:
    result = run.run_sync(agent, message_history)
    print(result.answer.content)
```

## 3. Setup Requirements

### System Prerequisites

- **Python subprocess module**: Built into Python (no additional installation needed)
- **Shell access**: Command prompt (Windows) or terminal (macOS/Linux)
- **Appropriate permissions**: Ensure your Python script can execute shell commands

### Platform Compatibility

The integration works across different operating systems:
- **Windows**: Uses Command Prompt or PowerShell commands
- **macOS**: Uses bash or zsh commands
- **Linux**: Uses bash or other available shells

### No External Dependencies

This integration uses only Python standard library modules:
- `subprocess` - for executing shell commands
- `platform` - for detecting the operating system

## 4. Usage Examples

### System Information

```python
# Get system details
user_prompt = "Show me the current system information including OS version and available disk space"
```

### File Management

```python
# Navigate and explore directories
user_prompt = "List all Python files in the current directory and show their sizes"
```

### Development Workflows

```python
# Run development commands
user_prompt = "Check if git is available, and if so, show the current git status"
```

### Process Management

```python
# Monitor system processes
user_prompt = "Show me the top 5 processes using the most CPU"
```

### Getting Help

- **Examples**: Check out the complete example at `examples/integrations/shell_integration.py`
- **Python subprocess docs**: [subprocess documentation](https://docs.python.org/3/library/subprocess.html)
- **Platform detection**: [platform module documentation](https://docs.python.org/3/library/platform.html)

---
