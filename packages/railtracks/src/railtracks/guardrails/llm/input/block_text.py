from __future__ import annotations

import re

from railtracks.guardrails.core.decision import GuardrailDecision
from railtracks.guardrails.core.event import LLMGuardrailEvent
from railtracks.guardrails.llm.concrete import InputGuard
from railtracks.llm.message import Role

_SCANNABLE_ROLES = frozenset({Role.user, Role.system})


class BlockTextInputGuard(InputGuard):
    """Blocks LLM input when any user or system message matches a regex pattern."""

    def __init__(
        self,
        pattern: str,
        *,
        name: str | None = None,
        fail_open: bool = False,
        user_facing_message: str | None = None,
    ) -> None:
        """Initialize the input block-text guard.

        Args:
            pattern: Regex pattern; if it matches any scannable message content
                the guard returns ``BLOCK``.
            name: Optional rail name for traces (see :class:`InputGuard`).
            fail_open: Whether to allow the request to continue when this guard raises an unexpected exception.
            user_facing_message: Optional message surfaced to UIs and
                visualizers when the guard blocks.

        Raises:
            re.error: If *pattern* is not a valid regular expression.
        """
        super().__init__(name=name, fail_open=fail_open)
        self._pattern = re.compile(pattern)
        self._user_facing_message = user_facing_message

    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        """Block if any user/system string message matches the pattern.

        Returns:
            ``BLOCK`` when the pattern is found, ``ALLOW`` otherwise.
        """
        for msg in event.messages:
            if msg.role not in _SCANNABLE_ROLES or not isinstance(msg.content, str):
                continue
            if self._pattern.search(msg.content):
                return GuardrailDecision.block(
                    reason=("Input blocked: prohibited content detected."),
                    user_facing_message=self._user_facing_message,
                )
        return GuardrailDecision.allow(reason="No blocked patterns detected in input.")
