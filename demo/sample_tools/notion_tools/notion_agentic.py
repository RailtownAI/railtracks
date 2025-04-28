from typing import Any, Dict
import src.requestcompletion as rc
from src.requestcompletion.llm import MessageHistory, UserMessage
from src.requestcompletion.nodes.library import from_function
from .notion import find_page, create_page, add_block, find_user, tag_user

class NotionAgenticTool(rc.library.ToolCallLLM):
    def __init__(self, message_history: MessageHistory):
        super().__init__(message_history=message_history, 
                         model=rc.llm.OpenAILLM("gpt-4o"),  # or any other model you want to use
                         )

    # define a set of tools that the agent can use
    def connected_nodes(self):  
        return {
            from_function(find_page),   # make a node from a function in one line 🥰
            from_function(create_page),
            from_function(add_block),
            from_function(find_user),
            from_function(tag_user),
            }
    
    # =================== If this node is a tool, then it needs to implement the following ==================
    @classmethod
    def tool_info(cls) -> rc.llm.Tool:
        return rc.llm.Tool(
            name="NotionAgenticTool",
            detail="A notion tool that can find pages, create pages, add blocks, find users, and tag users.",
            parameters={rc.llm.Parameter(name="notion_task_request", param_type="string", description="The detailed task prompt for the task to be completed.")},
        )

    @classmethod
    def prepare_tool(cls, tool_parameters: Dict[str, Any]):
        message_hist = MessageHistory(
            [UserMessage(f"Request Prompt: '{tool_parameters['notion_task_request']}'")]
        )
        return cls(message_hist)
    # ===========================================================================================================

    @classmethod
    def pretty_name(cls) -> str:
        return "Notion Agentic Tool"
