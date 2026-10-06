"""Triage a support inbox with a System One decision model.

System One (S1) models read a piece of text and answer typed questions about it with
calibrated probabilities instead of prose: a yes/no (Noul), a pick from named labels
(Choice), or a level on a rubric (Score). One request answers every question in a
single forward pass, typically in well under a second.

This example triages support tickets with TypeSafe's Jev:

1. the model   -> `rt.decisions.TypeSafeAI`; swapping hosts is one line
2. the schema  -> a `TypeSafeSchema` subclass whose attributes are the questions
3. the node    -> `rt.decision_node`, the S1 counterpart of `rt.agent_node`
4. using it    -> as a Flow, routing an inbox on the probabilities, as an agent's
                  tool, and as a direct call

Decision nodes record each request (`decision.*` events), so `railtracks viz` shows it
with its answers, latency and cost.

Needs TYPESAFE_API_KEY, plus OPENAI_API_KEY for the agent.

Run: uv run python examples/s1/s1_demo.py
"""

import asyncio

import railtracks as rt

TypeSafeSchema = rt.decisions.TypeSafeSchema

##### 1. The model #####

jev = rt.decisions.TypeSafeAI(model_name="jev-latest")  # reads TYPESAFE_API_KEY

# Every /v1/systemone host takes the same schema; pass any of these as `model=` below.
jev_via_openrouter = rt.decisions.OpenRouterAI(model_name="typesafe/jev-1.13")
solar = rt.decisions.UpstageAI(model_name="solar-decide")  # reads UPSTAGE_API_KEY
kev = rt.decisions.TypeSafeCompatibleAI(  # any other compatible server
    model_name="jaredpalmer/kev-4b", api_base="http://localhost:8008"
)

##### 2. The schema: each attribute is one question #####


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


##### 3. The node #####

# Typed as a node returning DecisionResponse[Triage]. As a tool, it takes the ticket
# text as `state`, and its description lists the questions.
TriageTicket = rt.decision_node("Triage Ticket", model=jev, schema=Triage)

##### 4. Using it #####

TICKETS = [
    "I was charged twice for my March invoice. Please refund the duplicate.",
    "Your API has returned 502s for an hour and our checkout is down. FIX THIS NOW.",
    "We're a team of 40. Is there volume pricing on the Business plan?",
    "Hey, is the annual plan cheaper than monthly? Also exports seem slow lately.",
]

CONFIDENT = 0.8


@rt.function_node
async def route_inbox(tickets: list[str]) -> dict[str, list[str]]:
    """Sort tickets into team queues: urgent tickets go first, unclear ones to a person.

    Args:
        tickets (list[str]): The raw ticket texts.
    """
    results = await rt.call_batch(TriageTicket, tickets)  # in parallel, one per ticket
    queues: dict[str, list[str]] = {"needs_a_person": []}
    for ticket, result in zip(tickets, results):
        # call_batch hands back a failed call's exception in place of its result
        if isinstance(result, Exception):
            queues["needs_a_person"].append(ticket)
            continue
        department = result.structured.department
        if department.probabilities[department.choice] < CONFIDENT:
            queues["needs_a_person"].append(ticket)
            continue
        queue = queues.setdefault(department.choice, [])
        if result.structured.is_urgent.noul >= CONFIDENT:
            queue.insert(0, ticket)
        else:
            queue.append(ticket)
    return queues


SupportAgent = rt.agent_node(
    "Support Agent",
    llm=rt.llm.OpenAILLM("gpt-5.4-mini"),
    system_message=(
        "Call Triage Ticket on the ticket before replying. It returns probabilities: "
        "if no department is at least 0.8 likely, say a person will pick the ticket "
        "up. Then draft a short reply from the right team."
    ),
    tool_nodes=[TriageTicket],  # the agent reads the response's one-line str()
)

triage_flow = rt.Flow(name="Ticket Triage", entry_point=TriageTicket)
inbox_flow = rt.Flow(name="Inbox Routing", entry_point=route_inbox)
support_flow = rt.Flow(name="Support Agent", entry_point=SupportAgent)

if __name__ == "__main__":
    # One ticket in, a DecisionResponse[Triage] out. str() is the one-line summary:
    # is_urgent: yes 0.99 | department: technical 1.00 | frustration: 2.0/2
    result = triage_flow.invoke(TICKETS[1])
    print(result)

    # Each attribute is typed as its answer (NoulAnswer, ChoiceAnswer, ScoreAnswer):
    # {'billing': 0.0, 'technical': 1.0, 'sales': 0.0} and {0: 0.0, 1: 0.02, 2: 0.98}
    print(result.structured.department.probabilities)
    print(result.structured.frustration.probabilities)
    # jev-1.13.0: 0.39s, $1.764e-05
    print(f"{result.model_name}: {result.latency:.2f}s, ${result.cost}")

    # Acting on the probabilities: confident tickets are routed, the rest escalated.
    # {'needs_a_person': [<annual plan + slow exports>], 'billing': [<charged twice>],
    #  'technical': [<502s, checkout down>], 'sales': [<volume pricing>]}
    print(inbox_flow.invoke(TICKETS))

    # As a tool, the decision grounds the agent's reply: no department reaches 0.8 for
    # this ticket, so the agent says a person will pick it up.
    print(support_flow.invoke(TICKETS[3]).text)

    # Outside a node, call the model directly, as with an LLM's achat. The state can
    # be JSON too. Direct calls aren't recorded; decision nodes are.
    # is_urgent: no 0.23 | department: billing 1.00 | frustration: 0.2/2
    ticket = {"subject": "Duplicate charge", "body": TICKETS[0]}
    print(asyncio.run(jev.aask(ticket, Triage)))
