import src.requestcompletion as rc
from src.requestcompletion.llm import MessageHistory, SystemMessage, UserMessage, AssistantMessage
from src.requestcompletion.config import ExecutorConfig
from examples.sample_agents import ImageAgent, NotionAgent, AudioAgent
from src.requestcompletion.nodes.library import from_function
from src.requestcompletion.visuals.agent_viewer import AgentViewer


USER_PROMPT = "Record my audio for 15 seconds and transcribe it."
"""
I have an image of a flowchart on a whiteboard, the image is saved as mermaid.jpeg under the assets folder, which is inside demo folder. 
Please transcribe the image as mermaid code and save it to the Test Page in Notion.
"""
async def top_level_node():
    audio_transcription_user_message = await rc.call(AudioAgent, 
                           message_history=MessageHistory([UserMessage(USER_PROMPT)]))
    
    image_transcription = await rc.call(ImageAgent, 
                           message_history=MessageHistory([UserMessage(audio_transcription_user_message.text)]))
    
    await rc.call(NotionAgent, message_history=MessageHistory([UserMessage(audio_transcription_user_message.text),
                                                               UserMessage(f"Transctiption text:  , {image_transcription.text}"),
                                                               UserMessage(f"Transctiption code:  , {image_transcription.code}"),
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