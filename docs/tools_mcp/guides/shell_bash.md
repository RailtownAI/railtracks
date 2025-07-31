# Shell Integration

Enable your Railtracks agents to execute shell commands and interact with your local system, automating tasks and retrieving system information.

**Version:** 0.0.1

## Table of Contents

- [1. What You Can Do](#1-what-you-can-do)
- [2. Quick Start](#2-quick-start)
- [3. Setup Requirements](#3-setup-requirements)
- [4. Usage Examples](#4-usage-examples)
- [5. Common Use Cases](#5-common-use-cases)
- [6. Security Considerations](#6-security-considerations)
- [7. Troubleshooting](#7-troubleshooting)

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

## 5. Common Use Cases

### Development Assistant

Create an agent that helps with development tasks:

```python
agent = tool_call_llm(
    connected_nodes={bash_tool},
    system_message=f"""You are a development assistant on a {platform.system()} machine. 
    Help with development tasks like running tests, checking code quality, managing git repositories, 
    and navigating project structures. Always explain what commands you're running and why.""",
    model=rt.llm.OpenAILLM("gpt-4o")
)
```

### System Administrator

Build an agent for system administration tasks:

```python
agent = tool_call_llm(
    connected_nodes={bash_tool},
    system_message=f"""You are a system administrator assistant on a {platform.system()} machine. 
    Help monitor system health, manage processes, check disk usage, and perform routine maintenance. 
    Be cautious with destructive commands and always explain potential risks.""",
    model=rt.llm.OpenAILLM("gpt-4o")
)
```

### File Organization Helper

Create an agent that helps organize and manage files:

```python
agent = tool_call_llm(
    connected_nodes={bash_tool},
    system_message=f"""You are a file organization assistant on a {platform.system()} machine. 
    Help users navigate directories, find files, organize content, and manage file systems. 
    Always ask for confirmation before moving or deleting files.""",
    model=rt.llm.OpenAILLM("gpt-4o")
)
```

### Build and Deployment Assistant

Build an agent for CI/CD and deployment tasks:

```python
agent = tool_call_llm(
    connected_nodes={bash_tool},
    system_message=f"""You are a build and deployment assistant on a {platform.system()} machine. 
    Help with running builds, executing tests, managing dependencies, and deployment processes. 
    Always verify commands before execution and explain each step.""",
    model=rt.llm.OpenAILLM("gpt-4o")
)
```

## 6. Security Considerations

### Important Security Notes

**⚠️ Security Warning**: Shell integration gives agents direct access to your system. Use with caution!

### Best Practices

1. **Limit Command Scope**: Consider restricting which commands can be executed
2. **Validate Input**: Add input validation to prevent malicious commands
3. **Use Specific System Messages**: Guide agents to be cautious with destructive operations
4. **Run in Controlled Environments**: Test in isolated environments first
5. **Monitor Command Execution**: Use verbose logging to track what commands are executed

### Enhanced Security Implementation

For production use, consider adding command restrictions:

```python
def run_shell_safe(command: str) -> str:
    """Run a shell command with basic safety checks."""
    # List of dangerous commands to block
    dangerous_commands = ['rm -rf', 'del /s', 'format', 'mkfs', 'dd if=']
    
    # Check for dangerous patterns
    if any(dangerous in command.lower() for dangerous in dangerous_commands):
        return "Error: Command blocked for security reasons"
    
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"Error: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out"
    except Exception as e:
        return f"Exception: {str(e)}"

# Use the safer version
bash_tool_safe = rt.library.from_function(run_shell_safe)
```

## 7. Troubleshooting

### Common Issues

**"Permission denied" errors**
- Ensure your Python script has appropriate permissions
- On Unix systems, you may need to modify file permissions with `chmod`
- Some commands may require administrator/root privileges

**Commands not found**
- Verify the command exists on your system
- Check your system's PATH environment variable
- Use full paths to executables if needed

**Platform-specific command issues**
- Windows uses different commands than Unix-like systems
- Use `platform.system()` to detect the OS and adjust commands accordingly
- Consider using cross-platform alternatives when available

**Timeout issues**
- Long-running commands may need timeout adjustments
- Consider breaking large tasks into smaller operations
- Use asynchronous execution for time-intensive tasks

### Platform-Specific Commands

**Windows Examples:**
```python
user_prompt = "Use 'dir' to list files and 'systeminfo' for system details"
```

**macOS/Linux Examples:**
```python
user_prompt = "Use 'ls -la' to list files and 'uname -a' for system details"
```

### Getting Help

- **Examples**: Check out the complete example at `examples/integrations/shell_integration.py`
- **Python subprocess docs**: [subprocess documentation](https://docs.python.org/3/library/subprocess.html)
- **Platform detection**: [platform module documentation](https://docs.python.org/3/library/platform.html)

---

*Last updated: July 29, 2025*