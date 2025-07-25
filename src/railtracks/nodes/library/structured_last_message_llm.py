from typing import TypeVar

from pydantic import BaseModel

from .structured_llm_base import StructuredLLM

_TOutput = TypeVar("_TOutput", bound=BaseModel)


class StructuredLastMessageLLM(StructuredLLM[_TOutput]):
    """A simple LLM node that takes in a message and schema and returns a
       structured response.

    This node accepts message_history in the following formats:
    - MessageHistory: A list of Message objects
    - UserMessage: A single UserMessage object
    - str: A string that will be converted to a UserMessage

    Examples:
        ```python
        # Using MessageHistory
        mh = MessageHistory([UserMessage("Tell me about the world around us")])
        result = await rc.call(TerminalLLM, user_input=mh)

        # Using UserMessage
        user_msg = UserMessage("Tell me about the world around us")
        result = await rc.call(TerminalLLM, user_input=user_msg)

        # Using string
        result = await rc.call(
            TerminalLLM, user_input="Tell me about the world around us"
        )
        ```
    """

    def return_output(self):
        return self.message_hist[-1].content
