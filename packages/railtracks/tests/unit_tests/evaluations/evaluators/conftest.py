from uuid import UUID, uuid4

import pytest

from railtracks.evaluations.point import (
    AgentDataPoint,
    LLMCall,
    LLMDetails,
    LLMIO,
    MessageRole,
    Status,
    ToolArguments,
    ToolCall,
    ToolDetails,
)


def make_llm_call(index: int = 0, input_tokens: int = 50, output_tokens: int = 10, total_cost: float = 0.001, latency: float = 1.2) -> LLMCall:
    return LLMCall(
        model_name="gpt-4",
        model_provider="OpenAI",
        input=[LLMIO(role=MessageRole.USER, content="What is the stock price?")],
        output=LLMIO(role=MessageRole.ASSISTANT, content="$100"),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_cost=total_cost,
        latency=latency,
        index=index,
    )


def make_tool_call(name: str = "get_price", runtime: float = 0.1, status: Status = Status.COMPLETED) -> ToolCall:
    return ToolCall(
        identifier=uuid4(),
        name=name,
        arguments=ToolArguments(args=[], kwargs={"ticker": "AMZN"}),
        output=214.88,
        runtime=runtime,
        status=status,
    )


def make_agent_data_point(
    agent_name: str = "TestAgent",
    llm_calls: list[LLMCall] | None = None,
    tool_calls: list[ToolCall] | None = None,
) -> AgentDataPoint:
    if llm_calls is None:
        llm_calls = [make_llm_call()]
    if tool_calls is None:
        tool_calls = [make_tool_call()]
    tool_names = {tc.name for tc in tool_calls}
    return AgentDataPoint(
        identifier=uuid4(),
        session_id=uuid4(),
        agent_name=agent_name,
        agent_input={"args": ["What is the stock price?"], "kwargs": {}},
        agent_output={"answer": "$100"},
        llm_details=LLMDetails(calls=llm_calls),
        tool_details=ToolDetails(tool_names=tool_names, calls=tool_calls),
    )


@pytest.fixture
def agent_data_point() -> AgentDataPoint:
    return make_agent_data_point()


@pytest.fixture
def two_agent_data_points() -> list[AgentDataPoint]:
    """Two data points — required by ToolUseEvaluator cross-run aggregation."""
    return [make_agent_data_point(), make_agent_data_point()]
