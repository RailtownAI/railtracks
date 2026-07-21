# --8<-- [start: setup]
import railtracks as rt
from railtracks.guardrails import (
    GuardrailBlockedError,
    GuardrailDecision,
    LLMGuardrailEvent,
)


# The quickest way to write a guard is the decorator API: a plain function that
# takes the guardrail event and returns a decision.
@rt.input_guard
def block_sensitive_requests(event: LLMGuardrailEvent) -> GuardrailDecision:
    """Check the latest user message and block requests that mention passwords."""
    latest_message = event.messages[-1]
    content = str(latest_message.content).lower()

    if "password" in content:
        return GuardrailDecision.block(
            reason="Requests for passwords are not allowed.",
            user_facing_message="Ask for something else instead.",
        )

    return GuardrailDecision.allow()


# Guards are model middleware — attach them with model_middleware=[...].
Agent = rt.agent_node(
    name="guardrails-quickstart-agent",
    llm=rt.llm.GeminiLLM("gemini-2.5-flash"),
    system_message="You are a concise assistant.",
    model_middleware=[block_sensitive_requests],
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
