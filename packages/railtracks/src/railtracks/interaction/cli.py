from typing import Literal, TypeVar

from railtracks.built_nodes.concrete.response import LLMResponse

from ..built_nodes.concrete._llm_base import LLMBase
from ..human_in_the_loop import CliUI
from ..utils.logging.create import get_rt_logger
from .interactive import _chat_ui_interactive

logger = get_rt_logger(__name__)

_TOutput = TypeVar("_TOutput", bound=LLMResponse)


async def cli(
    node: type[LLMBase[_TOutput, _TOutput, Literal[False]]],
    initial_message_to_user: str | None = None,
    initial_message_to_agent: str | None = None,
    turns: int | None = None,
    *args,
    **kwargs,
) -> _TOutput:
    """Starts an interactive CLI session with an LLM-based agent."""

    if not issubclass(node, LLMBase):
        raise ValueError(
            "Interactive sessions only support nodes that are children of LLMBase."
        )

    response = None

    try:
        logger.info("Connecting with CLI Session")

        chat_ui = CliUI()
        await chat_ui.connect()

        response = await _chat_ui_interactive(
            chat_ui,
            node,
            initial_message_to_user,
            initial_message_to_agent,
            turns,
            *args,
            **kwargs,
        )

    except Exception as e:
        logger.error(f"Error during CLI session: {e}")
    finally:
        return response  # type: ignore
