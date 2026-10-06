"""Triage support tickets with a self-hosted Laya decision model.

Laya serves the same `/v1/systemone` format as TypeSafe, so it takes the same
`TypeSafeSchema` questions. `rt.decisions.LayaAI` reads the server's URL from
LAYA_API_BASE (or `api_base=`) and the optional LAYA_API_KEY; without a key the request
is sent unauthenticated. Calls are priced from LiteLLM's catalog, where `laya/english`
is listed at $0 (you pay for your own hardware).

Laya answers all three question types. It caps a Choice at 100 options, a request at
64 questions and the state at 50,000 characters (TypeSafe allows 255 options); a
request over a limit fails before it is sent.

Needs a running Laya server (LAYA_API_BASE, default here http://localhost:8000):

    pip install "laya[serve]"
    laya-serve

See https://github.com/NandhaKishorM/laya/blob/main/docs/http-api.md.

Run: uv run python examples/s1/laya_example.py
"""

import os

import railtracks as rt

TypeSafeSchema = rt.decisions.TypeSafeSchema

laya = rt.decisions.LayaAI(
    model_name="english",  # Laya checkpoints: english, multilingual, typed-decisions
    api_base=os.environ.get("LAYA_API_BASE", "http://localhost:8000"),
)


class Triage(TypeSafeSchema):
    is_urgent = TypeSafeSchema.Noul(instructions="The message conveys urgency")
    department = TypeSafeSchema.Choice(
        instructions="Which team should handle this",
        criteria={
            "billing": "Charges, refunds, invoices, or plan changes",
            "technical": "Bugs, outages, errors, or integration problems",
            "sales": "Pricing questions, upgrades, or new purchases",
        },
    )
    frustration = TypeSafeSchema.Score(
        instructions="How frustrated the customer is",
        criteria=["Calm", "Frustrated but civil", "Very angry"],
    )


TriageTicket = rt.decision_node("Triage Ticket", model=laya, schema=Triage)
triage_flow = rt.Flow(name="Laya Ticket Triage", entry_point=TriageTicket)

if __name__ == "__main__":
    result = triage_flow.invoke("I was charged twice for my March invoice.")

    # one segment per question: "is_urgent: … | department: billing … | …"
    print(result)
    print("department probabilities:", result.structured.department.probabilities)
    # english via laya: $0.0 (litellm lists laya/* at zero; you pay for the hardware)
    print(f"{result.model_name} via {result.provider}: ${result.cost}")
