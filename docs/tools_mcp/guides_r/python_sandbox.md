# Python Sandbox Integration

Create Railtracks agents that can execute Python code safely in isolated Docker containers, enabling dynamic code generation, data analysis, and computational tasks.

**Version:** 0.0.1

---

## 1. What You Can Do

The Python Sandbox integration enables your Railtracks agents to:

- **Safe Code Execution**: Run Python code in isolated Docker containers
- **Dynamic Programming**: Generate and execute code based on user requests
- **Data Analysis**: Perform calculations, create visualizations, and analyze data
- **Package Management**: Install and use Python packages on-demand
- **Educational Tools**: Create interactive Python learning experiences
- **Prototyping**: Quickly test ideas and algorithms

## 2. Quick Start

Get your Python sandbox running in just a few steps:

### Step 1: Verify Docker is running

```bash
docker --version
# Should return Docker version information
```

### Step 2: Create a Python agent with sandbox capabilities

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

# Create your Python programming agent
agent = tool_call_llm(
    connected_nodes={execute_code},
    system_message="""You are a master Python programmer. To execute code, you have access to a sandboxed Python environment.
    You can execute code in it using execute_code.
    You can only see the output of the code if it is printed to stdout or stderr, so anything you want to see must be printed.
    You can install packages with code like 'import os; os.system("pip install numpy")'""",
    model=rt.llm.OpenAILLM("gpt-4o"),
)
```

### Step 3: Use your agent to execute Python code

```python
user_prompt = """Create a 3x3 array of random numbers using numpy, and print the array and its mean"""
message_history = rt.llm.MessageHistory()
message_history.append(rt.llm.UserMessage(user_prompt))

with rt.Runner() as run:
    create_sandbox_container()
    try:
        result = run.run_sync(agent, message_history)
        print(result.answer.content)
    finally:
        kill_sandbox()
```

## 3. Setup Requirements

### Docker Installation

The Python sandbox requires Docker to be installed and running:

**Windows:**
- Download [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop)
- Follow the installation instructions
- Ensure Docker is running (check system tray)

**macOS:**
- Download [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop)
- Install and start Docker Desktop

**Linux:**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install docker.io
sudo systemctl start docker
sudo systemctl enable docker

# Add your user to docker group (optional, to run without sudo)
sudo usermod -aG docker $USER
```

## 4. Usage Examples

### Data Analysis and Visualization

```python
user_prompt = """
Create a line chart showing the sine and cosine functions from 0 to 2π.
Use matplotlib and save the plot as 'trig_functions.png'.
Print confirmation when done.
"""
```

### Mathematical Computations

```python
user_prompt = """
Calculate the first 20 Fibonacci numbers and print them.
Then calculate and print the ratio of consecutive Fibonacci numbers 
to show how it approaches the golden ratio.
"""
```

### Package Installation and Usage

```python
user_prompt = """
Install pandas and create a DataFrame with sample sales data.
Calculate total sales by region and print a summary table.
"""
```

### Algorithm Implementation

```python
user_prompt = """
Implement a binary search algorithm and test it with a sorted list of numbers.
Print the search results for finding different values.
"""
```


### Getting Help

- **Examples**: Check out the complete example at `examples/integrations/sandbox_python_integration.py`
- **Docker Documentation**: [docs.docker.com](https://docs.docker.com/)
- **Python Docker Images**: [hub.docker.com/_/python](https://hub.docker.com/_/python)
