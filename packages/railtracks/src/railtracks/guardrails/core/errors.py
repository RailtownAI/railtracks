from __future__ import annotations

from typing import TYPE_CHECKING, Any

from railtracks.exceptions.errors import NodeInvocationError

if TYPE_CHECKING:
    from railtracks.guardrails.core.trace import GuardrailTrace


class GuardrailBlockedError(NodeInvocationError):
    """
    Raised when guardrails deterministically block an operation (e.g. LLM input).

    This error is intended to remain distinguishable from `LLMError` so callers/tests can
    assert guardrail rejection explicitly.
    """

    def __init__(
        self,
        *,
        rail_name: str | None = None,
        reason: str,
        user_facing_message: str | None = None,
        traces: list["GuardrailTrace"] | None = None,
        meta: dict[str, Any] | None = None,
        notes: list[str] | None = None,
        fatal: bool = False,
    ):
        """Create a block error with optional trace and user-facing context.

        Args:
            rail_name: Name of the rail that blocked, if known.
            reason: Machine-oriented explanation (also embedded in the base message).
            user_facing_message: Optional short text for clients or UIs.
            traces: Optional list of :class:`~railtracks.guardrails.core.trace.GuardrailTrace`
                from the failed run.
            meta: Optional structured details copied from the blocking decision.
            notes: Extra debug lines forwarded to :class:`NodeInvocationError`.
            fatal: Passed through to :class:`NodeInvocationError` (whether the run is
                considered unrecoverable).
        """
        self.rail_name = rail_name
        self.reason = reason
        self.user_facing_message = user_facing_message
        self.traces = traces
        self.meta = meta

        base_message = "Blocked by guardrails"
        if rail_name:
            base_message += f" ({rail_name})"
        base_message += f": {reason}"

        derived_notes: list[str] = []
        if user_facing_message:
            derived_notes.append(f"user_message={user_facing_message!r}")
        if meta:
            derived_notes.append("meta attached (see exception.meta)")

        super().__init__(
            message=base_message,
            notes=[*(notes or []), *derived_notes],
            fatal=fatal,
        )
