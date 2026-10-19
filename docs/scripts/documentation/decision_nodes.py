# --8<-- [start: schema]
import railtracks as rt

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
# --8<-- [end: schema]

# --8<-- [start: models]
# reads TYPESAFE_API_KEY
jev = rt.decisions.TypeSafeDecisions(model_name="jev-latest")

# reads OPENROUTER_API_KEY; OpenRouter model ids carry the vendor
jev_on_openrouter = rt.decisions.OpenRouterDecisions(model_name="typesafe/jev-1.13")

# reads OPENAI_API_KEY
luna = rt.decisions.OpenAIDecisions(model_name="gpt-6-luna")
# --8<-- [end: models]

# --8<-- [start: model_options]
jev_with_retries = rt.decisions.TypeSafeDecisions(
    model_name="jev-latest",
    timeout=10.0,  # seconds per request, default 30
    # retries rate limits, timeouts, dropped connections, 500 and 503
    retry_approach=rt.llm.retries.ExponentialRetry(max_tries=3),
)
# --8<-- [end: model_options]

# --8<-- [start: node]
TriageTicket = rt.decision_node("Triage Ticket", model=jev, schema=triage)
# --8<-- [end: node]

# --8<-- [start: flow]
triage_flow = rt.Flow(name="Ticket Triage", entry_point=TriageTicket)


def triage_ticket(ticket: str) -> None:
    result = triage_flow.invoke(ticket)
    # is_urgent: yes 0.99 | department: technical 1.00 | frustration: 2.0/2
    print(result)


# --8<-- [end: flow]


# --8<-- [start: answers]
def route(ticket: str) -> str:
    result = triage_flow.invoke(ticket)

    urgent = result.structured[is_urgent]  # PredicateAnswer
    team = result.structured[department]  # ChoiceAnswer
    mood = result.structured[frustration]  # ScoreAnswer

    if team.probabilities[team.choice] < 0.8:
        return "needs_a_person"
    if urgent.probability >= 0.8 or mood.score >= 1.5:
        return f"{team.choice} (priority)"
    return team.choice


# --8<-- [end: answers]


# --8<-- [start: json_state]
def triage_json() -> None:
    ticket = {
        "subject": "Duplicate charge",
        "body": "I was charged twice for my March invoice.",
    }
    result = triage_flow.invoke(ticket)
    print(result.structured[department].choice)


# --8<-- [end: json_state]


# --8<-- [start: batch]
@rt.function_node
async def triage_inbox(tickets: list[str]) -> list[str]:
    """Triage every ticket in parallel and return each one's department.

    Args:
        tickets (list[str]): The raw ticket texts.
    """
    results = await rt.call_batch(TriageTicket, tickets)
    departments = []
    for result in results:
        # call_batch returns a failed call's exception in place of its result
        if isinstance(result, Exception):
            departments.append("needs_a_person")
        else:
            departments.append(result.structured[department].choice)
    return departments


inbox_flow = rt.Flow(name="Inbox Triage", entry_point=triage_inbox)
# --8<-- [end: batch]

# --8<-- [start: agent_tool]
SupportAgent = rt.agent_node(
    "Support Agent",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message=(
        "Call Triage Ticket on the ticket before replying. If no department is at "
        "least 0.8 likely, say a person will pick the ticket up. Otherwise draft a "
        "short reply from the right team."
    ),
    tool_nodes=[TriageTicket],
)
support_flow = rt.Flow(name="Support Agent", entry_point=SupportAgent)
# --8<-- [end: agent_tool]


# --8<-- [start: errors]
@rt.function_node
async def safe_triage(ticket: str) -> str:
    """Triage a ticket, escalating to a person when the model can't answer.

    Args:
        ticket (str): The raw ticket text.
    """
    try:
        result = await rt.call(TriageTicket, ticket)
    except rt.exceptions.DecisionRefusalError as e:
        # e.refused names the declined questions; e.answers holds the rest
        return f"needs_a_person (declined: {', '.join(e.refused)})"
    except rt.exceptions.DecisionRateLimitError:
        return "retry_later"
    except rt.exceptions.DecisionModelError:
        return "needs_a_person"
    return result.structured[department].choice


# --8<-- [end: errors]


# --8<-- [start: retry_node]
RetriedTriage = rt.decision_node(
    "Triage Ticket",
    model=jev,
    schema=triage,
    # the node raises Decision*Error, not litellm's errors, so name them
    middleware=[
        rt.prebuilt.middleware.Retry(
            retry_on=(
                rt.exceptions.DecisionTimeoutError,
                rt.exceptions.DecisionRateLimitError,
            )
        )
    ],
)
# --8<-- [end: retry_node]


# --8<-- [start: direct]
async def ask_directly(ticket: str) -> None:
    try:
        result = await jev.aask(ticket, triage)
    except rt.decisions.DecisionProviderError as e:
        print(f"Decision failed: {e!r}")
        return
    print(result.structured[is_urgent].probability)


# --8<-- [end: direct]


# --8<-- [start: cost]
def report_cost(ticket: str) -> None:
    result = triage_flow.invoke(ticket)
    # jev-1.13.0 via typesafe: 420 input tokens, 0.39s, $1.764e-05
    print(
        f"{result.model_name} via {result.provider}: "
        f"{result.input_tokens} input tokens, {result.latency:.2f}s, ${result.cost}"
    )


# --8<-- [end: cost]


# --8<-- [start: node_middleware]
@rt.post_node
async def log_triage(
    result: rt.decisions.DecisionResponse,
) -> rt.decisions.DecisionResponse:
    print("triaged:", result)
    return result


LoggedTriage = rt.decision_node(
    "Triage Ticket", model=jev, schema=triage, middleware=[log_triage]
)
# --8<-- [end: node_middleware]
