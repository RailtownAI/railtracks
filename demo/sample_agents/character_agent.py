import sys
import os

# Add the parent directory of "demo" to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from demo.sample_tools.word_tools import check_chars
import src.requestcompletion as rc
from src.requestcompletion.llm import MessageHistory, SystemMessage, UserMessage
from src.requestcompletion.nodes.library import from_function
from src.requestcompletion.visuals.agent_viewer import AgentViewer

SYSTEM_PROMPT = SystemMessage(
    """
    You are a helpful agent that can check and find the number of instances of a certain
    character in a word. Make sure that you are always using the check_chars tool to find the 
    number of instances though.
    """
)
CharAgent = rc.library.tool_call_llm(
    pretty_name="Char Agent",
    system_message=SYSTEM_PROMPT,
    model=rc.llm.OpenAILLM(model_name="gpt-4o"),
    connected_nodes={
        from_function(check_chars),
    },
)

if __name__ == "__main__":
    USER_PROMPT = "How many r's are there in the word Strawberry"
    
    with rc.Runner() as runner:
        result = runner.run_sync(CharAgent,
                                 message_history=MessageHistory([UserMessage(USER_PROMPT)]))
        
    viewer = AgentViewer(
        stamps=result.all_stamps,
        request_heap=result.request_heap,
        node_heap=result.node_heap
    )
    viewer.display_graph()
        
    