"""Triage support tickets with Jev through OpenRouter.

OpenRouter serves System One models at `/api/v1/systemone`, with the vendor in the model
id (`typesafe/jev-1.13`). Its responses report what the call cost (`usage.cost`) and who
served it (`provider`), so the result's `cost` is what you were billed.

Needs OPENROUTER_API_KEY.

Run: uv run python examples/s1/openrouter_example.py
"""

import railtracks as rt

TypeSafeSchema = rt.decisions.TypeSafeSchema

jev = rt.decisions.OpenRouterAI(model_name="typesafe/jev-1.13")


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


TriageTicket = rt.decision_node("Triage Ticket", model=jev, schema=Triage)
triage_flow = rt.Flow(name="OpenRouter Ticket Triage", entry_point=TriageTicket)

if __name__ == "__main__":
    result = triage_flow.invoke(
        "Hey, is the annual plan cheaper than monthly? Also exports seem slow lately."
    )

    # is_urgent: no 0.17 | department: sales 0.47 | frustration: 0.3/2
    print(result)
    # No label reaches 0.8: the ticket mixes a pricing question with a performance one.
    # {'technical': 0.11, 'sales': 0.47, 'billing': 0.42}
    print(result.structured.department.probabilities)
    # typesafe/jev-1.13-20260917 via TypeSafe: $1.7388e-05
    print(f"{result.model_name} via {result.provider}: ${result.cost}")
