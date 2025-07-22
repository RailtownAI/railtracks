from typing import Type, Union, Literal
from pydantic import BaseModel
import json
from railtracks.llm import (
    MessageHistory,
    ModelBase,
    AssistantMessage,
)
from railtracks.nodes.library._tool_call_llm_base import (
    OutputLessToolCallLLM,
)

from railtracks.nodes.library._mcp_agent_base_class import (
    MCPAgentBase,
    check_output,
)

MCP_COMMAND = "npx"
MCP_ARGS = ["-y", "@notionhq/notion-mcp-server"]
DEFAULT_VERSION = "2022-06-28"
SYSTEM_MESSAGE = """You are a master notion page designer. You love creating beautiful
and well-structured Notion pages and make sure that everything is correctly formatted."""
PRETTY_NAME = "Notion Agent"
TOOL_DETAILS = """An AI assistant specialized in Notion page editing and management.
You can use this tool to edit and create any notion pages you might need."""


def notion_agent(  # noqa: C901
    notion_api_token: str | None = None,
    notion_version : str | None = None,
    model: ModelBase | None = None,
    output_type: Literal["MessageHistory", "LastMessage"] = "LastMessage",
    output_model: BaseModel | None = None,
) -> Type[OutputLessToolCallLLM[Union[MessageHistory, AssistantMessage, BaseModel]]]:
    """
    This function creates a notion agent class you can use to edit and
    create notion pages from a given root page specified in .env or message

    Args:
        notion_api_token: your notion api token, if not passed this will be taken from you .env
        notion_version: For you to specify the NotionMCP server notion if it is not up to date
        model:
            The type of LLM you would like to use
            output_type: Specifies what portion of the conversation to return. You can choose between
            the whole message history or just the most recent message.
        output_model: A parameter you can use to specify how you would like your output formatted.
    Returns:
        type: NotionAgent Class
    """

    #format the env variable
    if notion_version:
        headers = {
            "Authorization": f"Bearer {notion_api_token}",
            "Notion-Version": notion_version
        }
    else:
        headers = {
            "Authorization": f"Bearer {notion_api_token}",
            "Notion-Version": DEFAULT_VERSION
        }
    notion_env = {
        "OPENAPI_MCP_HEADERS": json.dumps(headers)
    }

    class NotionAgent(
        MCPAgentBase[check_output(output_type, output_model)],
        mcp_command=MCP_COMMAND,
        mcp_args=MCP_ARGS,
        mcp_env=notion_env,
        api_token=notion_api_token,
        pretty_name=PRETTY_NAME,
        model=model,
        system_message=SYSTEM_MESSAGE,
        output_type=output_type,
        output_model=output_model,
        tool_details=TOOL_DETAILS,
        tool_params=None,
    ):
        def connected_nodes(self):
            return self.__class__._connected_nodes

    return NotionAgent
