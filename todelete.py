import railtracks as rt
from railtracks.guardrails.llm._pii.config import PIIEntity, PIIRedactConfig
from railtracks.guardrails.llm.input.pii_redact import PIIRedactInputGuard
from railtracks.guardrails.llm.output.pii_redact import PIIRedactOutputGuard


agent = rt.agent_node(
    name="Guardrails Test Agent",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    model_middleware=[PIIRedactOutputGuard(PIIRedactConfig(entities=[PIIEntity.EMAIL_ADDRESS]))]
)


flow = rt.Flow(
    name="Guardrails Test Flow",
    entry_point=agent,
)

print(flow.invoke("Hello, my email is loganu@shaw.ca. Can you repeat back my email please?"))