import src.requestcompletion as rc
from src.requestcompletion.llm import MessageHistory, SystemMessage, UserMessage, AssistantMessage
from src.requestcompletion.config import ExecutorConfig
from audio_agent import AudioAgent
from notion_agent import NotionAgent
from src.requestcompletion.nodes.library import from_function
from src.requestcompletion.visuals.agent_viewer import AgentViewer


USER_PROMPT = "Record my audio for 10 seconds and transcribe it."


async def top_level_node():
    transcription = await rc.call(AudioAgent, 
                           message_history=MessageHistory([UserMessage(USER_PROMPT)]))
    
    await rc.call(NotionAgent, message_history=MessageHistory([UserMessage(transcription.text)]))


if __name__ == "__main__":
    TopAgent = from_function(top_level_node)

    with rc.Runner(executor_config=ExecutorConfig(timeout=50)) as runner:
        result = runner.run_sync(TopAgent)

    viewer = AgentViewer(
        stamps=result.all_stamps,
        request_heap=result.request_heap,
        node_heap=result.node_heap
    )
    viewer.display_graph()