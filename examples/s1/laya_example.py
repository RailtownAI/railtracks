"""Route support tickets with a self-hosted Laya decision model.

Laya serves the same `/v1/systemone` format as TypeSafe, so the same
`rt.classifiers.TypeSafeAI` client reaches it: point `api_base` at the server and set
`provider="laya"`. The provider prices calls from LiteLLM's catalog (`laya/english`
is listed at $0, since you pay for your own hardware) and reads LAYA_API_KEY, which
is optional; without it the request is sent unauthenticated.

Laya answers all three question types; this asks a single Choice question. Laya caps
a Choice at 100 options (TypeSafe allows 255), so a larger one fails at call time.

Needs a running Laya server (LAYA_API_BASE, default http://localhost:8000):

    pip install "laya[serve]"
    laya-serve

See https://github.com/NandhaKishorM/laya/blob/main/docs/http-api.md.

Run: uv run python examples/s1/laya_example.py
"""

import os

import railtracks as rt

TypeSafeSchema = rt.classifiers.TypeSafeSchema

laya = rt.classifiers.TypeSafeAI(
    model_name="english",  # Laya checkpoints: english, multilingual, typed-decisions
    provider="laya",
    api_base=os.environ.get("LAYA_API_BASE", "http://localhost:8000"),
)


class Routing(TypeSafeSchema):
    department = TypeSafeSchema.Choice(
        instructions="Choose the department that should help",
        criteria={
            "billing": "Invoices, payments, and refunds",
            "technical": "Bugs and connectivity problems",
        },
    )


RouteTicket = rt.decision_node("Route Ticket", model=laya, schema=Routing)
routing_flow = rt.Flow(name="Laya Ticket Routing", entry_point=RouteTicket)

if __name__ == "__main__":
    result = routing_flow.invoke("My invoice has two identical charges")

    print(result)  # department: billing 0.97
    print("department probabilities:", result.structured.department.probabilities)
    print(f"{result.model_name} via {laya.provider}: cost ${result.cost}")
