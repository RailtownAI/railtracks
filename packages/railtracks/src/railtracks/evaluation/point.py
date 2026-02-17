import json
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from rich import print
from tqdm import tqdm

from railtracks.utils.logging import get_rt_logger

logger = get_rt_logger(__name__)


class NodeType(str, Enum):
    AGENT = "Agent"
    TOOL = "Tool"


class NodeDataPoint(BaseModel):
    """A data point specific to any node execution."""

    identifier: str
    node_type: NodeType
    name: str
    details: dict[str, Any]


class Status(str, Enum):
    OPEN = "Open"
    COMPLETED = "Completed"
    FAILED = "Failed"


class EdgeDataPoint(BaseModel):
    """A data point specific to any node execution."""

    identifier: str
    source: str | None
    target: str
    details: dict[str, Any]


class ToolArguments(BaseModel):
    """Represents the arguments passed to a tool."""

    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """A tool used by an agent."""

    identifier: str
    name: str
    arguments: ToolArguments
    output: Any
    runtime: float
    status: Status


class ToolDetails(BaseModel):
    """Tool details for an agent, including all tool calls made."""

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
    input_tokens: int | None
    output_tokens: int | None
    total_cost: float | None
    latency: float | None
    index: int


class LLMDetails(BaseModel):
    """Details about an LLM call."""

    calls: list[LLMCall]


class AgentDataPoint(BaseModel):
    """A data point specific to agent interactions."""

    identifier: str
    agent_name: str
    agent_input: dict | list
    agent_output: dict | list | None
    llm_details: LLMDetails
    tool_details: ToolDetails


def extract_llm_details(llm_details: list[dict]) -> LLMDetails:
    calls = []
    for idx, detail in enumerate(llm_details):
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
        calls.append(
            LLMCall(
                model_name=detail.get("model_name", ""),
                model_provider=detail.get("model_provider", ""),
                input=inputs,
                output=output,
                input_tokens=detail.get("input_tokens", None),
                output_tokens=detail.get("output_tokens", None),
                total_cost=detail.get("total_cost", None),
                latency=detail.get("latency", None),
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
    except (json.JSONDecodeError, IOError):
        raise ValueError(f"Error loading session file: {path}")
    return session_data


def construct_graph(
    edges: dict[tuple[str | None, str], EdgeDataPoint],
) -> tuple[dict[str | None, list[str]], dict[str, list[EdgeDataPoint]]]:
    """Constructs a graph representation from the list of edges.

    Args:
        edges: Dictionary of edges with keys as (source, target) and values as EdgeDataPoint instances.
    Returns:
        A tuple containing:
            - graph: A dictionary representing the adjacency list of the graph, where keys are source node identifiers and values are lists of target node identifiers.
            - sink_list: A dictionary where keys are target node identifiers and values are lists of EdgeDataPoint instances that have that target.
    """
    graph: dict[str | None, list[str]] = defaultdict(list)
    sink_list: dict[str, list[EdgeDataPoint]] = defaultdict(list)

    for edge in edges.values():
        graph[edge.source].append(edge.target)
        sink_list[edge.target].append(edge)
    return graph, sink_list


def extract_tool_details(
    nodes: dict[str, NodeDataPoint],
    edges: dict[tuple[str | None, str], EdgeDataPoint],
    graph: dict[str | None, list[str]],
    agent_id: str,
) -> ToolDetails:
    """Extracts tool details for a given agent based on the graph structure.

    Args:
        nodes: Dictionary of node identifiers to NodeDataPoint instances.
        edges: Dictionary of edges with keys as (source, target) and values as EdgeData
        graph: Adjacency list representation of the graph.
        agent_id: Identifier of the agent node for which to extract tool details.
    Returns:
        ToolDetails instance containing details of all tool calls made by the agent.
    """
    tools = []
    for target_id in graph[agent_id]:
        target = nodes[target_id]
        edge = edges[(agent_id, target_id)]
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
                .get("total_time", 0),
                status=Status(edge.details.get("status")),
            )
        )
    return ToolDetails(calls=tools)


def extract_agent_io(
    sink_list: dict[str, list[EdgeDataPoint]], node: NodeDataPoint, file_path: str
) -> tuple[dict, dict]:
    """
    Extracts the input and output for an agent node based on its incoming edges.

    Args:
        sink_list: A dictionary where keys are target node identifiers and values are lists of EdgeDataPoint instances that have that target.
        node: The NodeDataPoint instance representing the agent node for which to extract input and output.
        file_path: The path to the session file being processed (used for logging).
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
                    f"Duplicate edge with id: {edge.identifier} for source: {edge.source} and target: {edge.target} in session file {file_path}."
                )
    return agent_input, agent_output


def extract_agent_data_points(session_files: list[str]) -> list[AgentDataPoint]:
    """
    Extract AgentDataPoint instances from session JSON files.

    This function processes Railtracks session JSON files and creates AgentDataPoint
    instances for each agent execution found. It extracts agent inputs, outputs, and
    internals (including LLM metrics if available).

    Args:
        session_files: List of paths to session JSON files (as strings or Path objects)

    Returns:
        List of AgentDataPoint instances, one for each agent execution found in the files.
        Returns empty list if no valid agent data is found.
    """
    data_points = []

    for file_path in tqdm(session_files, desc="Processing session files"):
        try:
            session_data = load_session(file_path)
        except (FileNotFoundError, ValueError) as e:
            logger.error(str(e))
            continue
        runs = session_data.get("runs", [])

        if len(runs) == 0:
            logger.warning(f"Session file {file_path} contains no runs")
        if len(runs) > 1:
            logger.warning(f"Session file {file_path} contains multiple runs")

        for run in runs:
            nodes = {
                node["identifier"]: NodeDataPoint(
                    identifier=node["identifier"],
                    node_type=NodeType(node["node_type"]),
                    name=node["name"],
                    details=node.get("details", {}),
                )
                for node in run.get("nodes", [])
            }

            edges = {
                (edge["source"], edge["target"]): EdgeDataPoint(
                    identifier=edge["identifier"],
                    source=edge["source"],
                    target=edge["target"],
                    details=edge.get("details", {}),
                )
                for edge in run.get("edges", [])
            }

            graph, sink_list = construct_graph(edges)

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
                        sink_list, node, file_path
                    )

                    data_points.append(
                        AgentDataPoint(
                            identifier=node.identifier,
                            agent_name=node.name,
                            agent_input=agent_input,
                            agent_output=agent_output,
                            llm_details=llm_details,
                            tool_details=tool_details,
                        )
                    )

    return data_points


if __name__ == "__main__":
    import railtracks as rt

    rt.enable_logging()
    session_files = [
        ".railtracks/data/sessions/Stock Analysis_0fe000df-04ae-43cd-9c14-cc4418f306df.json",
        ".railtracks/data/sessions/Case3-2-agent-tool-wrapped-func_427c5242-ee8a-43c0-aea3-2037921ba681.json",
    ]
    data_points = extract_agent_data_points(session_files)
    for dp in data_points:
        print(dp.agent_name)
