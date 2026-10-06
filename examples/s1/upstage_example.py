"""Triage support tickets with Upstage's Solar Decide.

Upstage serves Solar Decide on its own API at `/v1/systemone`, in the same format as
TypeSafe (https://console.upstage.ai/api/systemone), so the same schema works. Solar
Decide scores a Choice from single-token labels, so it takes at most 26 options; a
larger Choice fails before the request is sent.

Needs UPSTAGE_API_KEY. LiteLLM's price list has no Solar Decide entry yet, so `cost` is
None on this route. Through OpenRouter it's priced from what OpenRouter reports:
`rt.decisions.OpenRouterAI(model_name="upstage/solar-decide")`.

Run: uv run python examples/s1/upstage_example.py
"""

import railtracks as rt

TypeSafeSchema = rt.decisions.TypeSafeSchema

solar = rt.decisions.UpstageAI(model_name="solar-decide")


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


TriageTicket = rt.decision_node("Triage Ticket", model=solar, schema=Triage)
triage_flow = rt.Flow(name="Upstage Ticket Triage", entry_point=TriageTicket)

if __name__ == "__main__":
    result = triage_flow.invoke(
        "Your API has returned 502s for an hour and our checkout is down. FIX THIS NOW."
    )

    print(result)
    print("department probabilities:", result.structured.department.probabilities)
    print(f"{result.model_name} via {result.provider}: {result.latency:.2f}s")
