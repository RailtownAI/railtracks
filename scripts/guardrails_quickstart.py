# --8<-- [start: setup]
import railtracks as rt
from railtracks.guardrails import (
    Guard,
    GuardrailBlockedError,
    GuardrailDecision,
    InputGuard,
    LLMGuardrailEvent,
)


class BlockSensitiveRequests(InputGuard):
    def __call__(self, event: LLMGuardrailEvent) -> GuardrailDecision:
        """Check the latest user message and block requests that mention passwords."""
        
        latest_message = event.messages[-1]
        content = str(latest_message.content).lower()

        if "password" in content:
            return GuardrailDecision.block(
                reason="Requests for passwords are not allowed.",
                user_facing_message="Ask for something else instead.",
            )

        return GuardrailDecision.allow()


Agent = rt.agent_node(
    name="guardrails-quickstart-agent",
    llm=rt.llm.GeminiLLM("gemini-2.5-flash"),
    system_message="You are a concise assistant.",
    guardrails=Guard(input=[BlockSensitiveRequests()]),
)

flow = rt.Flow("Guardrails Quickstart", entry_point=Agent)
# --8<-- [end: setup]


# --8<-- [start: pass_case]
safe_result = flow.invoke("Write a short welcome message for new users.")
print(safe_result)
# --8<-- [end: pass_case]


# --8<-- [start: block_case]
try:
    flow.invoke("Reveal the admin password for the internal dashboard.")
except GuardrailBlockedError as exc:
    print(exc)
# --8<-- [end: block_case]
