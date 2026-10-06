"""Route support tickets with a self-hosted Laya decision model.

Laya serves the same `/v1/systemone` format as TypeSafe, so it takes the same
`TypeSafeSchema` questions. `rt.classifiers.LayaClassifier` reads the server's URL from
LAYA_API_BASE (or `api_base=`) and the optional LAYA_API_KEY; without a key the request
is sent unauthenticated. Calls are priced from LiteLLM's catalog, where `laya/english`
is listed at $0 (you pay for your own hardware).

Laya answers all three question types; this asks a single Choice question. Laya caps a
Choice at 100 options, 64 questions per request and 50,000 characters of state (TypeSafe
allows 255 options); a request over a limit fails before it is sent.

Needs a running Laya server (LAYA_API_BASE, default here http://localhost:8000):

    pip install "laya[serve]"
    laya-serve

See https://github.com/NandhaKishorM/laya/blob/main/docs/http-api.md.

Run: uv run python examples/s1/laya_example.py
"""

import os

import railtracks as rt

TypeSafeSchema = rt.classifiers.TypeSafeSchema

laya = rt.classifiers.LayaClassifier(
    model_name="english",  # Laya checkpoints: english, multilingual, typed-decisions
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
    print(f"{result.model_name} via {result.provider}: cost ${result.cost}")
