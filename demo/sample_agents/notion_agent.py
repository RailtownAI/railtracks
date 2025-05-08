from demo.sample_tools.notion_tools import find_page, create_page, add_block, find_user, tag_user
import src.requestcompletion as rc
from src.requestcompletion.llm import MessageHistory, SystemMessage, UserMessage
from src.requestcompletion.nodes.library import from_function
from src.requestcompletion.visuals.agent_viewer import AgentViewer

SYSTEM_PROMPT = SystemMessage(
    """
    You are a helpful assistant that can create and manage Notion pages.
    If you are asked to provide code blocks, ensure you are not including any markdown formatting.
    If you are provided a parent page name, always find the exact page name using the find_page tool before proceeding.
    """
)
NotionAgent = rc.library.tool_call_llm(
    pretty_name="Notion Agent",
    system_message=SYSTEM_PROMPT,
    model=rc.llm.OpenAILLM(model_name="gpt-4o"),
    connected_nodes={
        from_function(find_page),
        from_function(create_page),
        from_function(add_block),
        from_function(find_user),
        from_function(tag_user),
    },
)

if __name__ == "__main__":
    USER_PROMPT = "Create a new Notion page with the title 'Test Page' under `Agent Demo Root` and add a python code block with the text 'print(\"Hello World\")'."
    
    with rc.Runner() as runner:
        result = runner.run_sync(NotionAgent,
                                 message_history=MessageHistory([UserMessage(USER_PROMPT)]))
        
    viewer = AgentViewer(
        stamps=result.all_stamps,
        request_heap=result.request_heap,
        node_heap=result.node_heap
    )
    viewer.display_graph()
        
    