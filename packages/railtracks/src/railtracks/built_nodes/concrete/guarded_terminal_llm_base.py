from __future__ import annotations

import asyncio
from abc import ABC
from typing import Literal, TypeVar

from railtracks.exceptions import LLMError
from railtracks.guardrails.core import Guard, GuardRunner, GuardrailBlockedError
from railtracks.llm.response import Response

from ._llm_base import StringOutputMixIn
from .response import StringResponse
from .terminal_llm_base import TerminalLLMBase
from railtracks.guardrails.core.event import LLMGuardrailEvent, LLMGuardrailPhase

_TStream = TypeVar("_TStream", Literal[True], Literal[False])


class GuardedTerminalLLMBase(TerminalLLMBase[StringResponse, StringResponse, _TStream], ABC):
    """
    Terminal LLM base that evaluates input guardrails before invoking the model.

    NOTE: We intentionally evaluate guardrails outside the model-call try/except so
    `GuardrailBlockedError` is not wrapped into `LLMError`.
    """

    guardrails: Guard | None = None

    def _apply_input_guardrails(self) -> None:
        guard = self.__class__.guardrails
        if guard is None or not guard.input:
            return

        event = LLMGuardrailEvent(
            phase=LLMGuardrailPhase.INPUT,
            messages=self.message_hist,
            node_name=self.__class__.name(),
            node_uuid=self.uuid,
            model_name=getattr(self.llm_model, "model_name", lambda: None)(),
            model_provider=str(
                getattr(self.llm_model, "model_provider", lambda: None)()
            ),
            tags={"agent_kind": "terminal"},
        )

        new_messages, traces, decision = GuardRunner(guard).run_llm_input(event)

        # If rails transformed the prompt, apply it to this node instance only.
        self.message_hist = new_messages

        if decision is None:
            return

        if decision.action.value != "block":
            return

        rail_name = traces[-1].rail_name if traces else None
        raise GuardrailBlockedError(
            rail_name=rail_name,
            reason=decision.reason,
            user_facing_message=decision.user_facing_message,
            traces=traces,
            meta=decision.meta,
        )


class GuardedTerminalLLM(StringOutputMixIn, GuardedTerminalLLMBase[Literal[False]]):
    async def invoke(self):
        # Guardrails first (must not be wrapped into LLMError).
        self._apply_input_guardrails()

        try:
            returned_mess = await asyncio.to_thread(
                self.llm_model.chat, self.message_hist
            )
        except Exception as e:
            raise LLMError(
                reason=f"Exception during llm model chat: {str(e)}",
                message_history=self.message_hist,
            )

        if isinstance(returned_mess, Response):
            self._handle_output(returned_mess.message)
            return self.return_output(returned_mess.message)

        raise LLMError(
            reason="ModelLLM returned an unexpected message type.",
            message_history=self.message_hist,
        )


# Streaming guarded terminal LLM intentionally deferred.
# TODO(phase-1.5): implement GuardedStreamingTerminalLLM when streaming guardrails are prioritized.
