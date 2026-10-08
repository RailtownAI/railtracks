"""Triage support tickets with OpenAI's Decisions API (gpt-6-luna).

OpenAI's Decisions API (`POST /v1/decisions`, public beta) answers the same
`DecisionSchema` as the System One vendors: a Predicate (yes/no), a Choice and a Score,
with answers of the same types (`PredicateAnswer`, `ChoiceAnswer`, `ScoreAnswer`). The
call goes through `litellm.adecisions` as `openai/gpt-6-luna`. Unlike the System One
vendors, the input can also include images, sent as user messages with base64 data URLs.

The model may decline a question; that raises `DecisionRefusalError` from a node
(`DecisionProviderRefusalError` from a direct `aask`). `.refused` names the declined
questions and `.answers` holds the answers it did give.

Needs OPENAI_API_KEY. Decisions bill input tokens only ($0.10 per 1M on gpt-6-luna).

Run: uv run python examples/s1/openai_example.py
"""

import railtracks as rt

luna = rt.decisions.OpenAIDecisions(model_name="gpt-6-luna")  # reads OPENAI_API_KEY


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


TriageTicket = rt.decision_node("Triage Ticket", model=luna, schema=triage)
triage_flow = rt.Flow(name="OpenAI Ticket Triage", entry_point=TriageTicket)

if __name__ == "__main__":
    result = triage_flow.invoke(
        "Your API has returned 502s for an hour and our checkout is down. FIX THIS NOW."
    )

    # is_urgent: yes 1.00 | department: technical 1.00 | frustration: 1.5/2
    print(result)
    # {'billing': 0.0, 'technical': 1.0, 'sales': 0.0}
    print(result.structured[department].probabilities)
    # gpt-6-luna via openai: $4.21e-05
    print(f"{result.model_name} via {result.provider}: ${result.cost}")
