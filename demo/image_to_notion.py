import src.requestcompletion as rc
from src.requestcompletion.llm import MessageHistory, SystemMessage, UserMessage, AssistantMessage
from src.requestcompletion.config import ExecutorConfig
from examples.sample_agents import ImageAgent, NotionAgent
from src.requestcompletion.nodes.library import from_function
from src.requestcompletion.visuals.agent_viewer import AgentViewer


USER_PROMPT = "I have a sample flowchart I made on a whiteboard, the path to the image is 'demo/assets/mermaid.jpeg'. I want you to make a mermaid image out of it and us the NotionAgent save it to notion under a page called 'Agent Demo Root'."


async def top_level_node():
    transcription = await rc.call(ImageAgent, 
                           message_history=MessageHistory([UserMessage(USER_PROMPT)]))
    
    await rc.call(NotionAgent, message_history=MessageHistory([UserMessage(USER_PROMPT),
                                                               UserMessage(f"Transctiption text:  , {transcription.text}"),
                                                               UserMessage(f"Transctiption code:  , {transcription.code}"),
                                                               ]))


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