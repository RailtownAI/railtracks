from pydantic import BaseModel

from examples.sample_tools.audio_tools import record_audio, transcribe_audio

import src.requestcompletion as rc
from src.requestcompletion.llm import MessageHistory, SystemMessage, UserMessage, AssistantMessage
from src.requestcompletion.nodes.library import from_function

class AudioTranscription(BaseModel):
    user_voice_command: str

SYSTEM_PROMPT = SystemMessage(
    """
    You are a helpful assistant that can record users audio and transcribe it.
    """
)

AudioAgent = rc.library.tool_call_llm(
    pretty_name="Audio Agent",
    system_message=SYSTEM_PROMPT,
    model=rc.llm.OpenAILLM(model_name="gpt-4o"),
    connected_nodes=[
        from_function(record_audio),
        from_function(transcribe_audio),
    ],
    output_model=AudioTranscription,
)