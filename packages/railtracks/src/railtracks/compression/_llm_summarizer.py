

from hmac import new
import token
from typing import Callable


from railtracks.exceptions.errors import ContextCompressionError
from railtracks.interaction._call import call
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import Role, SystemMessage, UserMessage
from railtracks.llm.model import ModelBase

from ._base import ContextCompression


class LLMSummarizerCompression(ContextCompression):
    def __init__(self, llm: ModelBase, max_tokens: int, num_compressed_tokens: int = 500, retries: int = 4, name: str | None = None, system_message: str | None = None):
        from railtracks.built_nodes.easy_usage_wrappers.agent import agent_node
        self.num_compressed_tokens = num_compressed_tokens
        self.Agent = agent_node(name=name or self.default_name(), system_message=system_message or self.default_system_message(), llm=llm)
        self.retries = retries
        super().__init__(max_tokens=max_tokens)

    def default_system_message(self) -> str:
        return f"""You are a context compression assistant. You will be given a conversation history and must produce a single compressed summary of it.

Your summary will be injected as a system-level context block so the conversation can continue without the full history. Write it as a factual, third-person account of what has been discussed — not as a reply to the user.

Your summary must:
- Capture all decisions made, facts established, and key context from the exchange
- Preserve unresolved questions, pending tasks, and ongoing threads
- Retain specific values, names, identifiers, and data likely to be referenced later
- Note the current state of any multi-step process or problem being worked through

Your summary must be strictly under {self.num_compressed_tokens} tokens. This is a hard limit. Be dense — every token counts.

Output only the summary text with no preamble, headers, or meta-commentary."""


    @classmethod
    def default_name(cls) -> str:
        return "LLMSummarizerCompressionAgent"
    
    async def _compress(self, message_history: MessageHistory, token_counter: Callable[[str], int]) -> MessageHistory:
     
        # allow for a configurable number of retries in case the LLM does not meet the token requirements.
        retry_count = 0
        last_message = message_history[-1]
        if last_message.role == Role.user:
            working_history_message = self._convert_history_to_message(message_history.removed_system_messages()[:-1])
            working_message_history = MessageHistory([working_history_message])
        else:
            last_message = None 
            working_history_message = self._convert_history_to_message(message_history.removed_system_messages())
            working_message_history = MessageHistory([working_history_message])
        while True:
            result = await call(self.Agent, working_message_history)

            actual_tokens = token_counter(result.text)
            if actual_tokens <= self.num_compressed_tokens:
                
                break

            retry_count += 1
            if retry_count >= self.retries:
                raise ContextCompressionError(f"LLM summarization failed to meet token requirements after {self.retries} retries.")

            low = int(self.num_compressed_tokens * 0.9)
            working_message_history.append(result.message_history[-1])
            working_message_history.append(UserMessage(content=f"Your summary is {actual_tokens} tokens, which exceeds the limit. Please shorten it to under {self.num_compressed_tokens} tokens (target range: {low}–{self.num_compressed_tokens})."))

        # TODO: ensure the system message is not lost
        new_message_history = MessageHistory()
        new_message_history.extend([msg for msg in message_history if msg.role == Role.system])
        new_message_history.append(SystemMessage(content=f"The following is a compressed summary of the conversation so far:\n{result.text}"))
        if last_message is not None:
            new_message_history.append(last_message)
        return new_message_history
    
    @classmethod
    def _convert_history_to_message(cls, message_history: MessageHistory) -> UserMessage:
        # convert the message history to a single user message that can be sent to the LLM for summarization.
        # this is necessary because the summarization agent expects a single message as input.
        content = ""
        for message in message_history:
            content += f"{message.role.value}: {message.content}\n"
        return UserMessage(content=content)
    



