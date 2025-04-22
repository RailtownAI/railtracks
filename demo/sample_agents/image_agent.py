from pydantic import BaseModel

from demo.sample_tools.image_tools import parse_image_to_text, parse_image_to_mermaid, save_image, analyze_image

import src.requestcompletion as rc
from src.requestcompletion.llm import SystemMessage
from src.requestcompletion.nodes.library import from_function

class Transcription(BaseModel):
    text: str
    code: str | None = None

SYSTEM_PROMPT = SystemMessage(
    """
    You are a helpful assistant that can parse images(mermaid code and text), analyze images, and transcribe them.
    """
)

ImageAgent = rc.library.tool_call_llm(
    pretty_name="Image Agent",
    system_message=SYSTEM_PROMPT,
    model=rc.llm.OpenAILLM(model_name="gpt-4o"),
    connected_nodes=[
        from_function(parse_image_to_mermaid),
        from_function(parse_image_to_text),
        from_function(analyze_image),
        from_function(save_image),
    ],
    output_model=Transcription,
)