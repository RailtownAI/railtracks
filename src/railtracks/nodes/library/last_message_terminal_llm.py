from .terminal_llm_base import TerminalLLM


class LastMessageTerminalLLM(TerminalLLM[str]):
    """A simple LLM node that takes in a message and returns a response. It is the simplest of all LLMs.

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
