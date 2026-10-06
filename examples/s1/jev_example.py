"""Triage support tickets with TypeSafe's hosted Jev model.

One request answers all three questions about a ticket: a yes/no (Noul), a pick from
named labels (Choice) and a rubric level (Score), each as calibrated probabilities.
The decision node runs as a Flow's entry point, so the call is recorded with its cost
and shows up in `railtracks viz`.

Needs TYPESAFE_API_KEY.

Run: uv run python examples/s1/jev_example.py
"""

import railtracks as rt

TypeSafeSchema = rt.decisions.TypeSafeSchema

jev = rt.decisions.TypeSafeAI(
    model_name="jev-latest",
    # retries rate limits, timeouts, dropped connections and 5xx; not 4xx
    retry_approach=rt.llm.retries.ExponentialRetry(max_tries=3),
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


TriageTicket = rt.decision_node("Triage Ticket", model=jev, schema=Triage)
triage_flow = rt.Flow(name="Jev Ticket Triage", entry_point=TriageTicket)

if __name__ == "__main__":
    ticket = "Your API has returned 502s for an hour and our checkout is down."
    result = triage_flow.invoke(ticket)

    # is_urgent: yes 0.98 | department: technical 1.00 | frustration: 1.1/2
    print(result)
    # {'sales': 0.0, 'technical': 1.0, 'billing': 0.0}
    print("department probabilities:", result.structured.department.probabilities)
    # {0: 0.0, 1: 0.9, 2: 0.1}: frustrated but civil, without the all-caps
    print("frustration levels:", result.structured.frustration.probabilities)
    # jev-1.13.0: 416 tokens, $1.7472e-05
    print(f"{result.model_name}: {result.input_tokens} tokens, ${result.cost}")
