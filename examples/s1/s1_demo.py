"""System One (S1) decision models in railtracks.

Needs TYPESAFE_API_KEY to run (and OPENAI_API_KEY for the agent); importing it needs
neither. The design and the decisions behind it are on the "SystemOne Design" Notion
page (Scratchpad).

S1 models take a `state` (text or JSON) plus a schema of typed questions and return
calibrated probabilities instead of text. `rt.decision_node` is the S1 counterpart of
`rt.agent_node`: a model plus a schema in, a node out.

S1 models live in `rt.decisions`, the way chat models live in `rt.llm`. The question
types (Noul, Choice, Score) are TypeSafe's, so they sit in the `TypeSafeSchema`
namespace for now; if other vendors adopt the same format, the namespace goes generic.
`TypeSafeAI` speaks TypeSafe's `/v1/systemone` format, so it also reaches compatible
hosts such as OpenRouter or a self-hosted Kev server.
"""

import asyncio

import railtracks as rt

TypeSafeSchema = rt.decisions.TypeSafeSchema

##### 1. The model #####

jev = rt.decisions.TypeSafeAI(model_name="jev-latest")  # reads TYPESAFE_API_KEY

# Same format, other hosts: swap `model=jev` below for either of these.
solar = rt.decisions.OpenRouterClassifier(  # reads OPENROUTER_API_KEY
    model_name="upstage/solar-decide"
)
# Any other /v1/systemone server (here a self-hosted Kev) works through the base class.
kev = rt.decisions.SystemOneProvider(
    model_name="jaredpalmer/kev-4b", api_base="http://localhost:8008"
)

##### 2. The schema: a class whose attributes are the questions #####


# Each attribute's name is the question's name. On an answer, each attribute is typed
# as that question's answer (NoulAnswer, ChoiceAnswer, ScoreAnswer).
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

# Overloads type this as a node returning DecisionResponse[Triage], and reject a
# schema that doesn't match the model's vendor.
TriageTicket = rt.decision_node(
    "Triage Ticket",
    model=jev,
    schema=Triage,
)

TICKETS = [
    "I was charged twice for my March invoice. Please refund the duplicate.",
    "Your API has returned 502s for an hour and our checkout is down. FIX THIS NOW.",
    "We're a team of 40. Is there volume pricing on the Business plan?",
]

##### 4. Using it: Flow, call_batch, and as an agent's tool #####


@rt.function_node
async def urgent_tickets(tickets: list[str]) -> list[str]:
    """Return the tickets that are probably urgent, one decision request per ticket.

    Args:
        tickets (list[str]): The raw ticket texts.
    """
    results = await rt.call_batch(TriageTicket, tickets)
    # call_batch returns a failed call's exception in its slot instead of raising
    return [
        ticket
        for ticket, result in zip(tickets, results)
        if not isinstance(result, Exception) and result.structured.is_urgent.noul >= 0.8
    ]


SupportAgent = rt.agent_node(
    name="Support Agent",
    llm=rt.llm.OpenAILLM("gpt-5.4-mini"),
    system_message=(
        "Call Triage Ticket on each ticket first. It returns probabilities, so say "
        "when a result is uncertain. Then draft a short reply."
    ),
    tool_nodes=[TriageTicket],  # the agent reads the response's compact str()
)

triage_flow = rt.Flow(name="Ticket Triage", entry_point=TriageTicket)
urgent_flow = rt.Flow(name="Urgent Tickets", entry_point=urgent_tickets)
support_flow = rt.Flow(name="Support Agent", entry_point=SupportAgent)

if __name__ == "__main__":
    result = triage_flow.invoke(TICKETS[1])  # DecisionResponse[Triage]
    # is_urgent: yes 0.93 | department: technical 0.88 | frustration: 1.7/2
    print(result)
    print(result.structured.department.probabilities)  # {"technical": 0.88, ...}
    print(result.model_name, result.latency, result.cost)

    # The model can also be called directly, the way an LLM is called with achat.
    print(asyncio.run(jev.aask(TICKETS[0], Triage)))

    print(urgent_flow.invoke(TICKETS))
    print(support_flow.invoke(TICKETS[1]).text)
