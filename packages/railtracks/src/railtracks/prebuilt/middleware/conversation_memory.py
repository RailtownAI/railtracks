from __future__ import annotations

import uuid
from copy import deepcopy
from typing import Sequence

import railtracks.context as context
from railtracks.built_nodes.llm.response import LLMResponse
from railtracks.context.central import is_context_present
from railtracks.llm.history import MessageHistory
from railtracks.llm.message import Message, UserMessage
from railtracks.middleware.core import Middleware


def _continues(existing: MessageHistory, candidate: Sequence[object]) -> bool:
    """Return whether ``candidate`` already opens with every message in ``existing``.

    ``Message`` defines no ``__eq__``, so comparing the two lists directly is an
    identity check that fails the moment either side has been copied. Compare role
    and content instead, short-circuiting on identity for the common case.
    """
    if len(candidate) < len(existing):
        return False
    for stored, incoming in zip(existing, candidate):
        if stored is incoming:
            continue
        if not isinstance(incoming, Message):
            return False
        if stored.role != incoming.role or stored.content != incoming.content:
            return False
    return True


class ConversationMemory(Middleware):
    """Automatically cache and append conversation history across node invocations.

    Node-level middleware (``middleware=``). Automatically preserves multi-turn
    conversations in session context and prepends prior turns to incoming inputs.
    Do not manually pass prior message history into invocations when this middleware
    is attached, as history is accumulated automatically.

    See: https://docs.railtracks.org/documentation/agent_design/middleware/prebuilt/list/conversation_memory/

    Args:
        context_key: Optional explicit session context key for sharing, querying,
            or seeding history. If None, an isolated per-instance key is generated,
            which no external caller can address.
        max_messages: Optional limit on the number of recent messages to retain.
            ``None`` and ``0`` both mean no limit.

    Raises:
        ValueError: If ``context_key`` is blank or ``max_messages`` is negative.
    """

    def __init__(
        self,
        context_key: str | None = None,
        *,
        max_messages: int | None = None,
    ):
        if context_key is not None and not context_key.strip():
            raise ValueError("context_key must be a non-empty string when provided.")
        if max_messages is not None and max_messages < 0:
            raise ValueError(f"max_messages must not be negative, got {max_messages}.")

        self._instance_id = uuid.uuid4().hex[:8]
        self._context_key = context_key or f"conversation_history_{self._instance_id}"
        self._max_messages = max_messages or None
        self._state: dict[str, MessageHistory | None] = {"history": None}
        super().__init__(self._middleware_fn)

    @property
    def context_key(self) -> str:
        """The session context key holding the conversation history."""
        return self._context_key

    def get_history(self) -> MessageHistory | None:
        """Return the current conversation history from session context or instance."""
        return self._get_existing_history()

    def clear(self) -> None:
        """Clear the stored conversation history.

        The instance copy is always dropped. The session context entry is removed
        only when called during a run, since a finished run's context is no longer
        reachable from here: a ``FlowConnection`` held open on that run can still
        read the pre-clear value through ``conn.context``.
        """
        self._state["history"] = None
        if is_context_present():
            try:
                context.delete(self._context_key)
            except KeyError:
                pass

    def __deepcopy__(self, memo: dict) -> ConversationMemory:
        # ``Node.extend_middleware()`` copies the middleware already attached to a
        # node when ``rt.couple()`` layers another one on. The history dict is shared
        # by reference so the handle the caller holds keeps reading what the node
        # actually spends, rather than diverging from it once the run ends.
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if k == "_state":
                setattr(result, k, v)
            else:
                setattr(result, k, deepcopy(v, memo))
        return result

    def _extract_user_input(
        self, args: tuple[object, ...], kwargs: dict[str, object]
    ) -> tuple[bool, bool, object | None]:
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
            for msg in user_input:
                if isinstance(msg, Message):
                    history.append(msg)
        else:
            history.append(UserMessage(str(user_input)))

    def _combine_history(
        self, existing: MessageHistory, user_input: object
    ) -> MessageHistory:
        if isinstance(user_input, (list, MessageHistory)) and _continues(
            existing, user_input
        ):
            # The caller handed back history this middleware already holds, so the
            # input supersedes the stored copy rather than being appended to it.
            combined = MessageHistory(deepcopy(list(user_input)))
        else:
            combined = deepcopy(existing)
            self._append_to_history(combined, user_input)
        if self._max_messages is not None and len(combined) > self._max_messages:
            return MessageHistory(combined[-self._max_messages :])
        return combined

    def _get_existing_history(self) -> MessageHistory | None:
        if is_context_present():
            try:
                hist = context.get(self._context_key)
                if hist is not None:
                    return hist
            except KeyError:
                pass
        return self._state.get("history")

    def _save_result(self, result: object) -> None:
        if isinstance(result, LLMResponse):
            history = result.message_history
            if self._max_messages is not None and len(history) > self._max_messages:
                history = MessageHistory(history[-self._max_messages :])
            saved_copy = deepcopy(history)
            self._state["history"] = saved_copy
            if is_context_present():
                context.put(self._context_key, saved_copy)

    async def _middleware_fn(self, call, *args, **kwargs):
        existing = self._get_existing_history()
        has_input, is_pos, user_input = self._extract_user_input(args, kwargs)

        if has_input and existing:
            combined = self._combine_history(existing, user_input)
            if is_pos:
                args = (combined, *args[1:])
            else:
                kwargs = {**kwargs, "user_input": combined}

        result = await call(*args, **kwargs)
        self._save_result(result)
        return result
