import json
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from pydantic import BaseModel, Field

from railtracks.utils.logging import get_rt_logger

logger = get_rt_logger(__name__)


class NodeType(str, Enum):
    AGENT = "Agent"
    TOOL = "Tool"


class NodeDataPoint(BaseModel):
    """A data point specific to any node execution."""

    identifier: UUID
    node_type: NodeType
    name: str
    details: dict[str, Any]


class Status(str, Enum):
    OPEN = "Open"
    COMPLETED = "Completed"
    FAILED = "Failed"


class EdgeDataPoint(BaseModel):
    """A data point specific to any node execution."""

    identifier: UUID
    source: UUID | None
    target: UUID
    details: dict[str, Any]


class ToolArguments(BaseModel):
    """Represents the arguments passed to a tool."""

    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """A tool used by an agent."""

    identifier: UUID
    name: str
    arguments: ToolArguments
    output: Any
    runtime: float | None = None
    status: Status


class ToolDetails(BaseModel):
    """Tool details for an agent, including all tool calls made."""

    tool_names: set[str]
    calls: list[ToolCall]


class MessageRole(str, Enum):
    SYSTEM = "system"
    ASSISTANT = "assistant"
    USER = "user"
    TOOL = "tool"


class LLMIO(BaseModel):
    role: MessageRole
    content: list[dict] | dict | str  # tool call, tool response, message


class LLMCall(BaseModel):
    model_name: str
    model_provider: str
    input: list[LLMIO]
    output: LLMIO
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_cost: float | None = None
    latency: float | None = None
    index: int


class LLMDetails(BaseModel):
    """Details about an LLM call."""

    calls: list[LLMCall]


class AgentDataPoint(BaseModel):
    """A data point specific to agent interactions."""

    identifier: UUID
    session_id: UUID
    agent_name: str
    agent_input: dict | list
    agent_output: dict
    runtime: float | None = None
    llm_details: LLMDetails
    tool_details: ToolDetails


def extract_runtime(run: dict, session: dict) -> float | None:
    """Extract elapsed wall-clock time from run or legacy session boundaries."""
    if run.get("status") == Status.OPEN.value:
        return None

    timing = run if "start_time" in run or "end_time" in run else session
    start_time = timing.get("start_time")
    end_time = timing.get("end_time")

    if not isinstance(start_time, (int, float)) or not isinstance(
        end_time, (int, float)
    ):
        return None

    runtime = end_time - start_time
    return runtime if runtime >= 0 else None


def extract_llm_details(llm_details: list[dict]) -> LLMDetails:
    calls = []
    for idx, detail in enumerate(llm_details):
        try:
            inputs = [
                LLMIO(
                    role=MessageRole(message.get("role", "")),
                    content=message.get("content", ""),
                )
                for message in detail.get("input", [])
            ]
            output = detail.get("output", {})
            content = output.get("content")
            output = LLMIO(
                role=MessageRole(output.get("role", "")),
                content=content,
            )
        except Exception as e:
            logger.error(f"Error parsing LLM details at index {idx}: {e}")
            continue
        calls.append(
            LLMCall(
                model_name=detail.get("model_name", ""),
                model_provider=detail.get("model_provider", ""),
                input=inputs,
                output=output,
                input_tokens=detail.get("input_tokens"),
                output_tokens=detail.get("output_tokens"),
                total_cost=detail.get("total_cost"),
                latency=detail.get("latency"),
                index=idx,
            )
        )

    return LLMDetails(
        calls=calls,
    )


def load_session(path: str | Path) -> dict:
    """Loads a session JSON file and returns its content as a dictionary.

    Args:
        path: Path to the session JSON file.

    Returns:
        Dictionary containing the session data.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Session file not found: {path}")

    try:
        with open(path, "r") as f:
            session_data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        raise ValueError(f"Error loading session file: {path}. Details: {e}")
    return session_data


def construct_graph(
    edges: dict[tuple[UUID | None, UUID], EdgeDataPoint],
) -> tuple[dict[UUID | None, list[UUID]], dict[UUID, list[EdgeDataPoint]]]:
    """Constructs a graph representation from the list of edges.

    Args:
        edges: Dictionary of edges with keys as (source, target) and values as EdgeDataPoint instances.
    Returns:
        A tuple containing:
            - graph: A dictionary representing the adjacency list of the graph, where keys are source node identifiers and values are lists of target node identifiers.
            - sink_list: A dictionary where keys are target node identifiers and values are lists of EdgeDataPoint instances that have that target.
    """
    graph: dict[UUID | None, list[UUID]] = defaultdict(list)
    sink_list: dict[UUID, list[EdgeDataPoint]] = defaultdict(list)

    for edge in edges.values():
        graph[edge.source].append(edge.target)
        sink_list[edge.target].append(edge)
    return graph, sink_list


def extract_tool_details(
    nodes: dict[UUID, NodeDataPoint],
    edges: dict[tuple[UUID | None, UUID], EdgeDataPoint],
    graph: dict[UUID | None, list[UUID]],
    agent_id: UUID,
) -> ToolDetails:
    """Extracts tool details for a given agent based on the graph structure.

    Args:
        nodes: Dictionary of node identifiers to NodeDataPoint instances.
        edges: Dictionary of edges with keys as (source, target) and values as EdgeDataPoint instances.
        graph: Adjacency list representation of the graph.
        agent_id: Identifier of the agent node for which to extract tool details.
    Returns:
        ToolDetails instance containing details of all tool calls made by the agent.
    """
    tools = []
    names = set()
    for target_id in graph[agent_id]:
        target = nodes[target_id]
        edge = edges[(agent_id, target_id)]
        names.add(target.name)
        tools.append(
            ToolCall(
                identifier=target.identifier,
                name=target.name,
                arguments=ToolArguments(
                    args=edge.details.get("input_args", []),
                    kwargs=edge.details.get("input_kwargs", {}),
                ),
                output=edge.details.get("output", None),
                runtime=target.details.get("internals", {})
                .get("latency", {})
                .get("total_time"),
                status=Status(edge.details.get("status")),
            )
        )
    return ToolDetails(tool_names=names, calls=tools)


def extract_agent_io(
    sink_list: dict[UUID, list[EdgeDataPoint]], node: NodeDataPoint, session_id: str
) -> tuple[dict, dict]:
    """
    Extracts the input and output for an agent node based on its incoming edges.

    Args:
        sink_list: A dictionary where keys are target node identifiers and values are lists of EdgeDataPoint instances that have that target.
        node: The NodeDataPoint instance representing the agent node for which to extract input and output.
        session_id: The id of the session being processed (used for logging).
    Returns:
        A tuple containing:
            - agent_input: A dictionary with "args" and "kwargs" keys representing the input to the agent.
            - agent_output: The output of the agent, extracted from the edge details.
    """
    agent_input = {}
    agent_output = {}

    for edge in sink_list[node.identifier]:
        status = Status(edge.details.get("status"))
        if status == Status.COMPLETED:
            if agent_input == {} and agent_output == {}:
                agent_input = {
                    "args": edge.details.get("input_args", []),
                    "kwargs": edge.details.get("input_kwargs", {}),
                }
                agent_output = edge.details.get("output", {})
            else:
                logger.warning(
                    f"Duplicate edge with id: {edge.identifier} for source: {edge.source} and target: {edge.target} in session {session_id}."
                )
    return agent_input, agent_output


def resolve_file_paths(sources: list[str] | str) -> list[str]:
    """Resolves a directory path or list of file paths to a flat list of file paths.

    Args:
        sources: A directory path (str) whose files will be enumerated, or a list of file paths.

    Returns:
        List of resolved file path strings.

    Raises:
        FileNotFoundError: If a path does not exist.
        ValueError: If a str is not a directory, if a list item is a directory, or if no files are found.
        TypeError: If sources is not a str or list.
    """
    file_paths: list[str] = []

    if isinstance(sources, str):
        path = Path(sources)
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {sources}")
        if not path.is_dir():
            raise ValueError(
                f"A single string source must be a directory path; got a file: {sources}. "
                f'Wrap single files in a list: ["{sources}"].'
            )
        file_paths = [
            str(f) for f in path.iterdir() if f.is_file() and not f.name.startswith(".")
        ]
        logger.info(f"Found {len(file_paths)} files in directory: {sources}")
    elif isinstance(sources, list):
        for item in sources:
            item_path = Path(item)
            if item_path.is_dir():
                raise ValueError(
                    f"List items must be file paths, not directories: {item}"
                )
            if not item_path.is_file():
                raise FileNotFoundError(f"File does not exist: {item}")
        file_paths = sources
    else:
        raise TypeError(
            f"sources must be a string (directory) or list, got {type(sources)}"
        )

    if not file_paths:
        raise ValueError("No files found to process")

    return file_paths


def _data_points_from_payload(payload: dict) -> list[AgentDataPoint]:
    """Parse one in-memory session payload into a list of AgentDataPoint instances.

    Args:
        payload: A session dict with the shape produced by load_session (and by
            railtownai.get_agent_runs): {"session_id": ..., "runs": [...]}.

    Returns:
        AgentDataPoint instances for every agent execution in the payload. Empty list if
        the payload has no session_id or no runs.
    """
    session_id = payload.get("session_id")
    if session_id is None:
        logger.warning("no session_id found in payload, skipping.")
        return []

    runs = payload.get("runs", [])
    if len(runs) == 0:
        logger.warning(f"Session {session_id} contains no runs")
    if len(runs) > 1:
        logger.warning(f"Session {session_id} contains multiple runs")

    data_points: list[AgentDataPoint] = []
    for run in runs:
        nodes = {
            UUID(node["identifier"]): NodeDataPoint(
                identifier=node["identifier"],
                node_type=NodeType(node["node_type"]),
                name=node["name"],
                details=node.get("details", {}),
            )
            for node in run.get("nodes", [])
        }

        edges: dict[tuple[UUID | None, UUID], EdgeDataPoint] = {}
        for edge in run.get("edges", []):
            key = (
                (UUID(edge["source"]), UUID(edge["target"]))
                if edge["source"] is not None
                else (None, UUID(edge["target"]))
            )
            edges[key] = EdgeDataPoint(
                identifier=UUID(edge["identifier"]),
                source=UUID(edge["source"]) if edge["source"] is not None else None,
                target=UUID(edge["target"]),
                details=edge.get("details", {}),
            )

        graph, sink_list = construct_graph(edges)

        agent_nodes = [
            node for node in nodes.values() if node.node_type == NodeType.AGENT
        ]
        root_agent_ids = {
            target
            for source, target in edges
            if source is None
            and target in nodes
            and nodes[target].node_type == NodeType.AGENT
        }
        # Legacy payloads may omit graph edges; a lone agent is still the run root.
        if not root_agent_ids and len(agent_nodes) == 1:
            root_agent_ids.add(agent_nodes[0].identifier)

        run_runtime = extract_runtime(run, payload)
        for node in nodes.values():
            if node.node_type == NodeType.AGENT:
                llm_details_dict = node.details.get("internals", {}).get(
                    "llm_details", []
                )
                llm_details = (
                    extract_llm_details(llm_details_dict)
                    if llm_details_dict
                    else LLMDetails(calls=[])
                )

                tool_details = extract_tool_details(
                    nodes, edges, graph, node.identifier
                )

                agent_input, agent_output = extract_agent_io(
                    sink_list, node, session_id
                )

                data_points.append(
                    AgentDataPoint(
                        identifier=node.identifier,
                        session_id=UUID(session_id),
                        agent_name=node.name,
                        agent_input=agent_input,
                        agent_output=agent_output,
                        runtime=(
                            run_runtime if node.identifier in root_agent_ids else None
                        ),
                        llm_details=llm_details,
                        tool_details=tool_details,
                    )
                )

    return data_points


def extract_agent_data_points(
    sources: list[str] | str | list[dict],
) -> list[AgentDataPoint]:
    """Extract AgentDataPoint instances from session payloads or session JSON files.

    Args:
        sources: One of:
            - list[dict]: in-memory session payloads (e.g. from railtownai.get_agent_runs).
            - list[str]: file paths to session JSON files.
            - str: a directory path; all files inside are loaded.
            A single file or single payload must be wrapped in a list. Mixed lists of
            files and payloads are not supported.

    Returns:
        List of AgentDataPoint instances, one per agent execution found across all
        provided payloads. Returns an empty list if no valid agent data is found.
    """
    if isinstance(sources, list) and sources and isinstance(sources[0], dict):
        payloads: list[dict] = cast(list[dict], sources)
    else:
        file_sources = cast("list[str] | str", sources)
        payloads = []
        for file_path in resolve_file_paths(file_sources):
            try:
                payloads.append(load_session(file_path))
            except (FileNotFoundError, ValueError) as e:
                logger.error(str(e))

    data_points: list[AgentDataPoint] = []
    for payload in payloads:
        data_points.extend(_data_points_from_payload(payload))
    return data_points
