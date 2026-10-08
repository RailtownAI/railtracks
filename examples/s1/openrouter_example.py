"""Triage support tickets with Jev through OpenRouter.

OpenRouter serves System One models at its decisions endpoint, with the vendor in the
model id (`typesafe/jev-1.13`). The call goes through `litellm.adecisions` as
`openrouter/typesafe/jev-1.13`, and the result's `cost` is litellm's price for it
(input tokens only).

Needs OPENROUTER_API_KEY.

Run: uv run python examples/s1/openrouter_example.py
"""

import railtracks as rt

jev = rt.decisions.OpenRouterAI(model_name="typesafe/jev-1.13")


# Each question is an object with a name; the schema groups them by kind.
is_urgent = rt.decisions.Predicate(
    name="is_urgent", instructions="The message conveys urgency"
)
department = rt.decisions.Choice(
    name="department",
    instructions="Which team should handle this",
    choices={
        "billing": "Charges, refunds, invoices, or plan changes",
        "technical": "Bugs, outages, errors, or integration problems",
        "sales": "Pricing questions, upgrades, or new purchases",
    },
)
frustration = rt.decisions.Score(
    name="frustration",
    instructions="How frustrated the customer is",
    levels=["Calm", "Frustrated but civil", "Very angry"],
)
triage = rt.decisions.DecisionSchema(
    predicate=[is_urgent], choice=[department], score=[frustration]
)


TriageTicket = rt.decision_node("Triage Ticket", model=jev, schema=triage)
triage_flow = rt.Flow(name="OpenRouter Ticket Triage", entry_point=TriageTicket)

if __name__ == "__main__":
    result = triage_flow.invoke(
        "Hey, is the annual plan cheaper than monthly? Also exports seem slow lately."
    )

    # is_urgent: no 0.19 | department: sales 0.47 | frustration: 0.3/2
    print(result)
    # No label reaches 0.8: the ticket mixes a pricing question with a performance one.
    # {'billing': 0.39, 'technical': 0.14, 'sales': 0.47}
    print(result.structured[department].probabilities)
    # typesafe/jev-1.13-20260917 via openrouter: $1.7388e-05
    print(f"{result.model_name} via {result.provider}: ${result.cost}")
