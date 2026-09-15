from __future__ import annotations

from copy import deepcopy
from typing import Callable, MutableMapping

from railtracks.built_nodes.llm.response import LLMResponse
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import Message, UserMessage
from railtracks.middleware.core import Middleware

GLOBAL_CONVERSATION_STORE: dict[str, MessageHistory] = {}


class ConversationMemory(Middleware):
    """Automatically persist and append conversation history across node invocations.

    Node-level middleware (``middleware=``). Tracks conversation history in a
    shared or custom store and automatically prepends prior conversation turns
    to incoming inputs:

        import railtracks as rt
        from railtracks.prebuilt import middleware

        memory = middleware.ConversationMemory()
        Agent = rt.agent_node(
            "ChatAgent",
            llm=rt.llm.AnthropicLLM("claude-sonnet-4-6"),
            middleware=[memory],
        )

        res1 = await rt.call(Agent, "What is your name?")
        res2 = await rt.call(Agent, "What did I just ask?")  # Agent remembers!

    Args:
        session_key: Key used to identify the conversation in the store. Can be a
            static string or a zero-argument callable resolved dynamically on each
            invocation (e.g. ``lambda: rt.context.get("session_id", "default")``).
            Defaults to ``"default"``.
        store: Dictionary or mutable mapping used to store conversation histories.
            Defaults to the module-level ``GLOBAL_CONVERSATION_STORE`` if None.
        max_messages: Optional maximum number of recent messages to retain in
            history. If None, history is unbounded.
    """

    def __init__(
        self,
        session_key: str | Callable[[], str] = "default",
        *,
        store: MutableMapping[str, MessageHistory] | None = None,
        max_messages: int | None = None,
    ):
        self._session_key = session_key
        self._store = store if store is not None else GLOBAL_CONVERSATION_STORE
        self._max_messages = max_messages
        super().__init__(self._middleware_fn)

    @property
    def store(self) -> MutableMapping[str, MessageHistory]:
        """The underlying store holding conversation histories."""
        return self._store

    def _resolve_key(self) -> str:
        if callable(self._session_key):
            return str(self._session_key())
        return str(self._session_key)

    def get_history(self, session_key: str | None = None) -> MessageHistory | None:
        """Return the current message history for a session key."""
        key = session_key if session_key is not None else self._resolve_key()
        return self._store.get(key)

    def clear(self, session_key: str | None = None) -> None:
        """Clear conversation history for a specific key, or all keys if None."""
        if session_key is not None:
            self._store.pop(session_key, None)
        else:
            self._store.clear()

    def __deepcopy__(self, memo: dict) -> ConversationMemory:
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if k == "_store":
                setattr(result, k, v)
            else:
                setattr(result, k, deepcopy(v, memo))
        return result

    def _extract_user_input(
        self, args: tuple[object, ...], kwargs: dict[str, object]
    ) -> tuple[bool, bool, object]:
        if args:
            return True, True, args[0]
        if "user_input" in kwargs:
            return True, False, kwargs["user_input"]
        return False, False, None

    def _append_to_history(self, history: MessageHistory, user_input: object) -> None:
        if isinstance(user_input, str):
            history.append(UserMessage(user_input))
        elif isinstance(user_input, UserMessage):
            history.append(user_input)
        elif isinstance(user_input, (list, MessageHistory)):
            if len(user_input) >= len(history) and list(
                user_input[: len(history)]
            ) == list(history):
                del history[:]
                history.extend(user_input)
            else:
                for msg in user_input:
                    if isinstance(msg, Message):
                        history.append(msg)
        else:
            history.append(UserMessage(str(user_input)))

    def _combine_history(
        self, existing: MessageHistory, user_input: object
    ) -> MessageHistory:
        combined = deepcopy(existing)
        self._append_to_history(combined, user_input)
        if self._max_messages is not None and len(combined) > self._max_messages:
            return MessageHistory(combined[-self._max_messages :])
        return combined

    def _save_result(self, key: str, result: object) -> None:
        if isinstance(result, LLMResponse) and hasattr(result, "message_history"):
            history = result.message_history
            if self._max_messages is not None and len(history) > self._max_messages:
                history = MessageHistory(history[-self._max_messages :])
            self._store[key] = deepcopy(history)

    async def _middleware_fn(self, call, *args, **kwargs):
        key = self._resolve_key()
        existing = self._store.get(key)
        has_input, is_pos, user_input = self._extract_user_input(args, kwargs)

        if has_input and existing:
            combined = self._combine_history(existing, user_input)
            if is_pos:
                args = (combined, *args[1:])
            else:
                kwargs = {**kwargs, "user_input": combined}

        result = await call(*args, **kwargs)
        self._save_result(key, result)
        return result
