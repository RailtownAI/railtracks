"""The smallest harness that is still a harness: loop, tools, budget, record.

Points a read-only agent at this repository. Nothing here can mutate state, so
the only controls it needs are a turn budget and a deadline.

Run: uv run python examples/harness/minimal_harness.py
"""

import os
from pathlib import Path

import railtracks as rt
from railtracks.prebuilt.middleware import MaxCalls, Timeout

MODEL_NAME = os.environ.get("HARNESS_MODEL", "gpt-5.4-mini")
REPO_ROOT = Path(__file__).resolve().parents[2]

##### 1. Tool surface: read-only, three sharp tools #####


@rt.function_node
def list_files(directory: str) -> list[str]:
    """List the names of files and folders directly inside a repository directory.

    Args:
        directory (str): Path relative to the repository root, e.g. "packages/railtracks".
    """
    target = REPO_ROOT / directory
    return sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())


@rt.function_node
def read_file(path: str) -> str:
    """Read a UTF-8 text file from the repository.

    Args:
        path (str): Path relative to the repository root, e.g. "pyproject.toml".
    """
    return (REPO_ROOT / path).read_text(encoding="utf-8")


@rt.function_node
def find_files(pattern: str) -> list[str]:
    """Find repository files whose path matches a glob pattern.

    Args:
        pattern (str): Glob pattern relative to the repository root, e.g. "**/*.toml".
    """
    matches = (p for p in REPO_ROOT.glob(pattern) if p.is_file())
    return sorted(str(p.relative_to(REPO_ROOT)) for p in matches)[:100]


##### 2. The loop, with a budget and a deadline #####

RepoReader = rt.agent_node(
    name="Repo Reader",
    llm=rt.llm.OpenAILLM(MODEL_NAME),
    system_message=(
        "You answer questions about a Python repository. Locate files before reading them, "
        "read before you answer, and cite the paths you used."
    ),
    tool_nodes=[list_files, read_file, find_files],
    middleware=[Timeout(300)],
    model_middleware=[MaxCalls(20, custom_message="turn budget exhausted")],
)


##### 3. The record: save_state makes the run replayable in `railtracks viz` #####

if __name__ == "__main__":
    flow = rt.Flow("minimal-harness", entry_point=RepoReader, save_state=True)
    result = flow.invoke(
        "Which optional dependency extras does the railtracks package declare, and what is in each?"
    )

    print(result.text)
    print("\nRun `railtracks viz` to replay this run.")
