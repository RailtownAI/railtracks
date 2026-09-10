# --8<-- [start: loop]
from pathlib import Path

import railtracks as rt


@rt.function_node
def read_file(path: str) -> str:
    """Read a UTF-8 text file from disk.

    Args:
        path (str): Path of the file to read.
    """
    return Path(path).read_text(encoding="utf-8")


RepoReader = rt.agent_node(
    name="Repo Reader",
    llm=rt.llm.AnthropicLLM("claude-sonnet-5"),
    system_message="You answer questions about a repository. Read files before you answer.",
    tool_nodes=[read_file],
)

reader_flow = rt.Flow("repo-reader", entry_point=RepoReader)
answer = reader_flow.invoke("What package name does pyproject.toml declare?")
print(answer.text)
# --8<-- [end: loop]


# --8<-- [start: tools]
import shlex
import subprocess


@rt.function_node
def list_files(directory: str) -> list[str]:
    """List the file names directly inside a directory.

    Args:
        directory (str): Directory to list.
    """
    return sorted(p.name for p in Path(directory).iterdir())


# Left as a plain function on purpose: section 4 wraps it with a permission gate.
def run_shell(command: str) -> str:
    """Run a shell command and return its combined output.

    Args:
        command (str): Command to run, as it would be typed in a terminal.
    """
    finished = subprocess.run(
        shlex.split(command),
        capture_output=True,
        text=True,
        timeout=60,
    )
    return f"exit={finished.returncode}\n{finished.stdout}{finished.stderr}"


# --8<-- [end: tools]


# --8<-- [start: context]
todos = rt.prebuilt.tools.ToDoToolSet()
memory = rt.prebuilt.tools.KeyValueMemoryToolSet()

HARNESS_SYSTEM_MESSAGE = "\n\n".join(
    [
        "You are a repository assistant. Read before you write, and verify with tests.",
        rt.prebuilt.tools.ToDoToolSet.prompt(),
        rt.prebuilt.tools.KeyValueMemoryToolSet.prompt(),
    ]
)
# --8<-- [end: context]


# --8<-- [start: controls]
import asyncio

from railtracks.middleware import Verdict
from railtracks.prebuilt.middleware import MaxCalls, Timeout, pre_verifier

ALLOWED_EXECUTABLES = {"git", "ls", "pytest", "ruff"}


async def approve_shell(command: str) -> Verdict:
    """Allowlist the executable, then ask a human about the specific command."""
    parts = shlex.split(command)
    if not parts or parts[0] not in ALLOWED_EXECUTABLES:
        return Verdict(accepted=False, comment=f"{command!r} is not on the allowlist")

    # approve_fn runs on the event loop, so never block it with a bare input()
    answer = await asyncio.to_thread(input, f"Run `{command}`? [y/N] ")
    if answer.strip().lower() == "y":
        return Verdict(accepted=True)
    return Verdict(accepted=False, comment="declined by the operator")


gated_shell = rt.function_node(
    run_shell,
    name="run_shell",
    middleware=[pre_verifier(approve_shell), Timeout(90)],
)
# --8<-- [end: controls]


# --8<-- [start: record]
RepoHarness = rt.agent_node(
    name="Repo Harness",
    llm=rt.llm.AnthropicLLM("claude-sonnet-5"),
    system_message=HARNESS_SYSTEM_MESSAGE,
    tool_nodes=[
        read_file,
        list_files,
        gated_shell,
        *todos.tool_set(),
        *memory.tool_set(),
    ],
    middleware=[Timeout(600)],
    model_middleware=[MaxCalls(40, custom_message="model call budget exhausted")],
)

harness_flow = rt.Flow(
    "repo-harness",
    entry_point=RepoHarness,
    context={"repo_root": "."},
)


async def run_harness() -> None:
    outcome = await harness_flow.ainvoke(
        "Find the slowest unit test and explain why it is slow."
    )
    print(outcome.text)
    # every ToDoToolSet read is async, pretty_dashboard included
    print(await todos.pretty_dashboard())


asyncio.run(run_harness())
# --8<-- [end: record]
