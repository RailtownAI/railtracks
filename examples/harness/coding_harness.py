"""A coding harness: writes and shell commands, both behind a permission gate.

Shows the full set of harness parts on tools that actually mutate state:

- tool surface   -> read/write/list files, plus an allowlisted shell
- context        -> a todo list the agent revises, and key-value memory
- controls       -> path confinement, an executable allowlist, human approval,
                    a call budget, and deadlines
- record         -> every run replayable with `railtracks viz`

`write_file` is confined to a scratch workspace (override with HARNESS_WORKSPACE):
paths that escape it are rejected before the request reaches the filesystem.
`run_shell` is NOT a sandbox. It only sets `cwd`, and an interpreter the agent is
allowed to run (`python`, or `pytest` executing test files the agent just wrote)
can reach the rest of the disk. That is exactly why every shell call stops for
approval: the human is the real control here, not the allowlist.

Run: uv run python examples/harness/coding_harness.py
"""

import asyncio
import os
import shlex
import subprocess
import tempfile
from pathlib import Path

import railtracks as rt
from railtracks.middleware import Verdict
from railtracks.prebuilt.middleware import MaxCalls, Timeout, pre_verifier

MODEL_NAME = os.environ.get("HARNESS_MODEL", "claude-sonnet-5")
WORKSPACE = Path(
    os.environ.get(
        "HARNESS_WORKSPACE", Path(tempfile.gettempdir()) / "harness_workspace"
    )
)
ALLOWED_EXECUTABLES = {"git", "ls", "pytest", "python", "ruff"}


def _resolve_in_workspace(path: str) -> Path:
    """Resolve a model-supplied path, refusing anything outside the workspace.

    Args:
        path (str): Path as the model supplied it, relative to the workspace root.

    Raises:
        ValueError: If the resolved path falls outside the workspace.
    """
    resolved = (WORKSPACE / path).resolve()
    if not resolved.is_relative_to(WORKSPACE.resolve()):
        raise ValueError(f"{path!r} resolves outside the workspace")
    return resolved


##### 1. Controls: an allowlist, then a human, before anything mutates #####


async def _ask(prompt: str) -> bool:
    """Prompt the operator without blocking the event loop.

    `approve_fn` runs on the loop thread, so a bare `input()` would stall every
    other in-flight node until the human answers.

    Args:
        prompt (str): Question to show the operator.
    """
    answer = await asyncio.to_thread(input, prompt)
    return answer.strip().lower() == "y"


async def approve_write(path: str, content: str) -> Verdict:
    """Ask the operator to approve a file write, showing what will change."""
    print(f"\n--- write {path} ({len(content)} chars) ---\n{content[:400]}\n---")
    if await _ask(f"Write {path}? [y/N] "):
        return Verdict(accepted=True)
    return Verdict(accepted=False, comment="declined by the operator")


async def approve_shell(command: str) -> Verdict:
    """Allowlist the executable, then ask the operator about the exact command."""
    parts = shlex.split(command)
    if not parts:
        return Verdict(accepted=False, comment="empty command")
    if parts[0] not in ALLOWED_EXECUTABLES:
        return Verdict(
            accepted=False,
            comment=f"{parts[0]!r} is not on the allowlist: {sorted(ALLOWED_EXECUTABLES)}",
        )

    if await _ask(f"\nRun `{command}` in the workspace? [y/N] "):
        return Verdict(accepted=True)
    return Verdict(accepted=False, comment="declined by the operator")


##### 2. Tool surface: reads are free, writes are gated #####


@rt.function_node
def list_workspace(directory: str = ".") -> list[str]:
    """List the files and folders directly inside a workspace directory.

    Args:
        directory (str): Path relative to the workspace root. Defaults to the root.
    """
    target = _resolve_in_workspace(directory)
    return sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())


@rt.function_node
def read_file(path: str) -> str:
    """Read a UTF-8 text file from the workspace.

    Args:
        path (str): Path relative to the workspace root.
    """
    return _resolve_in_workspace(path).read_text(encoding="utf-8")


@rt.function_node(middleware=[pre_verifier(approve_write), Timeout(30)])
def write_file(path: str, content: str) -> str:
    """Create or overwrite a UTF-8 text file in the workspace.

    Args:
        path (str): Path relative to the workspace root.
        content (str): Full new contents of the file. Overwrites, never appends.
    """
    target = _resolve_in_workspace(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"wrote {len(content)} chars to {path}"


@rt.function_node(middleware=[pre_verifier(approve_shell), Timeout(120)])
def run_shell(command: str) -> str:
    """Run a shell command with the workspace as the working directory.

    Only these executables are permitted: git, ls, pytest, python, ruff. Every
    call needs operator approval before it runs.

    Args:
        command (str): Command to run, as it would be typed in a terminal.
    """
    finished = subprocess.run(
        shlex.split(command),
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return f"exit={finished.returncode}\n{finished.stdout}{finished.stderr}"


##### 3. Context: a plan the agent can revise, and facts that outlive a turn #####

todos = rt.prebuilt.tools.ToDoToolSet()
memory = rt.prebuilt.tools.KeyValueMemoryToolSet()

SYSTEM_MESSAGE = "\n\n".join(
    [
        "You are a coding agent working inside a scratch workspace. Plan before you act, "
        "read a file before you overwrite it, and verify your work by running the tests. "
        "Write and shell tools need operator approval, so batch your requests and explain "
        "each one before asking.",
        rt.prebuilt.tools.ToDoToolSet.prompt(),
        rt.prebuilt.tools.KeyValueMemoryToolSet.prompt(),
    ]
)

CodingHarness = rt.agent_node(
    name="Coding Harness",
    llm=rt.llm.AnthropicLLM(MODEL_NAME),
    system_message=SYSTEM_MESSAGE,
    tool_nodes=[
        list_workspace,
        read_file,
        write_file,
        run_shell,
        *todos.tool_set(),
        *memory.tool_set(),
    ],
    middleware=[Timeout(900)],
    # Caps model calls inside one run; the counter starts fresh each run.
    # Budgets belong in model_middleware: the node slot does not enforce (see #1560).
    model_middleware=[MaxCalls(40, custom_message="model call budget exhausted")],
)


##### 4. The record #####


async def main() -> None:
    """Run the harness once, then print the plan it worked through."""
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    print(f"Workspace: {WORKSPACE}")

    flow = rt.Flow(
        "coding-harness",
        entry_point=CodingHarness,
        context={"workspace": str(WORKSPACE)},
    )
    result = await flow.ainvoke(
        "Write a fizzbuzz(n) function in fizzbuzz.py, write pytest tests for it in "
        "test_fizzbuzz.py, then run the tests and report the outcome."
    )

    print(f"\n{result.text}")
    print(f"\n{await todos.pretty_dashboard()}")
    print("\nRun `railtracks viz` to replay this run.")


if __name__ == "__main__":
    asyncio.run(main())
