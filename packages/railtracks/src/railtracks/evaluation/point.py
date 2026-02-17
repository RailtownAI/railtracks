from pydantic import BaseModel, Field, field_serializer
from typing import Any, Literal
from uuid import UUID, uuid4
from pathlib import Path
import json
from enum import Enum
from collections import defaultdict
from railtracks.utils.logging import get_rt_logger
from rich import print
from tqdm import tqdm
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
    Failed = "Failed"


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
    content: list[dict] | dict | str # tool call, tool response, message


class LLMCall(BaseModel):
    model_name: str
    model_provider: str
    input: list[LLMIO]
    output: LLMIO
    input_tokens: int | None
    output_tokens: int | None
    total_cost: float | None
    latency: float | None


class LLMDetails(BaseModel):
    """Details about an LLM call."""
    calls: list[LLMCall]


class AgentDataPoint(BaseModel):
    """A data point specific to agent interactions."""

    identifier: UUID
    agent_name: str
    agent_input: dict | list
    agent_output: dict | list | None
    llm_details: LLMDetails
    tool_details: ToolDetails
    # agent_internals: dict[str, Any]

    # @field_serializer("agent_output", when_used="json")
    # def serialize_output(self, value: Any) -> Any:
    #     """Serialize BaseModel instances to dicts for JSON."""
    #     if isinstance(value, BaseModel):
    #         return value.model_dump(mode="json")
    #     return value


def extract_llm_details(llm_details: list[dict]) -> LLMDetails:
    calls = []
    for detail in llm_details:
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
            content=(
                [c for c in content]
                if isinstance(content, list)
                else content
            ),
        )
        calls.append(LLMCall(
            model_name=detail.get("model_name",""),
            model_provider=detail.get("model_provider", ""),
            input = inputs,
            output=output,
            input_tokens=detail.get("input_tokens",0),
            output_tokens=detail.get("output_tokens",0),
            total_cost=detail.get("total_cost",0),
            latency=detail.get("latency",0)
        ))
    
    return LLMDetails(
        calls=calls,
    )

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

    Example:
        >>> files = ["session1.json", "session2.json"]
        >>> data_points = extract_agent_data_points(files)
        >>> for dp in data_points:
        ...     print(f"Agent: {dp.agent_name}, Input: {dp.agent_input}")
    """
    data_points = []

    for file_path in tqdm(session_files, desc="Processing session files"):
        path = Path(file_path)
        if not path.exists():
            continue

        try:
            with open(path, "r") as f:
                session_data = json.load(f)
        except (json.JSONDecodeError, IOError):
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

            graph: dict[str | None, list[str]] = defaultdict(list)

            for edge in edges.values():
                graph[edge.source].append(edge.target)

            for node in nodes.values():
                if node.node_type == NodeType.AGENT:
                    llm_details_dict = node.details.get("internals", {}).get(
                        "llm_details", []
                    )
                    llm_details = extract_llm_details(llm_details_dict) if llm_details_dict else LLMDetails(calls=[])

                    # traverse the graph to find tools used by this agent
                    tools = []
                    for target_id in graph[node.identifier]:
                        target = nodes[target_id]
                        edge = edges[(node.identifier, target_id)]
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
                                status=Status(edge.details["status"]),
                            )
                        )

                    tool_details = ToolDetails(calls=tools)

                    data_points.append(
                        AgentDataPoint(
                            identifier=UUID(node.identifier),
                            agent_name=node.name,
                            agent_input=llm_details_dict[0].get("input", []), # the first LLM call input is considered the agent input
                            agent_output=llm_details_dict[-1].get("output", {}), # the last LLM call output is considered the agent output
                            llm_details=llm_details,
                            tool_details=tool_details,
                        )
                    )
                else:
                    continue
    return data_points


if __name__ == "__main__":
    # Example usage
    import railtracks as rt

    rt.enable_logging()
    session_files = [
        ".railtracks/data/sessions/Stock Analysis_0fe000df-04ae-43cd-9c14-cc4418f306df.json",
        ".railtracks/data/sessions/Case3-2-agent-tool-wrapped-func_427c5242-ee8a-43c0-aea3-2037921ba681.json",
        ".railtracks/data/sessions/Case5-toolception_63c43ec7-6068-4c61-86e7-8be673bdf13f.json",
    ]
    data_points = extract_agent_data_points(session_files)
    for dp in data_points:
        print(dp.agent_name)
