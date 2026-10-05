"""Triage support tickets with TypeSafe's hosted Jev model.

One request answers all three questions about a ticket: a yes/no (Noul), a pick from
named labels (Choice) and a rubric level (Score), each as calibrated probabilities.
The decision node runs as a Flow's entry point, so the call is recorded with its cost
and shows up in `railtracks viz`.

Needs TYPESAFE_API_KEY.

Run: uv run python examples/s1/jev_example.py
"""

import railtracks as rt

TypeSafeSchema = rt.classifiers.TypeSafeSchema

jev = rt.classifiers.TypeSafeAI(
    model_name="jev-latest",
    retry_approach=rt.llm.retries.ExponentialRetry(max_tries=3),  # 429s, timeouts, 5xx
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

    print(result)  # is_urgent: yes 0.97 | department: technical 0.95 | ...
    print("department probabilities:", result.structured.department.probabilities)
    print("frustration levels:", result.structured.frustration.probabilities)
    print(f"{result.model_name}: {result.input_tokens} tokens, ${result.cost}")
