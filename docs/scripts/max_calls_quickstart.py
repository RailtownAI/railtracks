# --8<-- [start: setup]
import railtracks as rt
from railtracks.prebuilt.middleware import MaxCalls, MaxCallsExceededError

# One budget instance shared by both tools: three searches per run between them,
# not three each. Pass a separate MaxCalls to each node to give them own limits.
search_budget = MaxCalls(
    max_calls=3,
    custom_message="search budget exhausted for this run",
)


def web_search(query: str) -> str:
    """Stand-in for a metered API you would rather not call without a cap."""
    return f"web results for {query!r}"


def image_search(query: str) -> str:
    """A second tool billed against the same budget."""
    return f"image results for {query!r}"


WebSearch = rt.function_node(web_search, middleware=[search_budget])
ImageSearch = rt.function_node(image_search, middleware=[search_budget])
# --8<-- [end: setup]


# --8<-- [start: flow]
@rt.function_node
async def research(topic: str) -> list[str]:
    """Work through four searches against a budget that only covers three."""
    plan = [
        (WebSearch, topic),
        (ImageSearch, topic),
        (WebSearch, f"{topic} reviews"),
        (ImageSearch, f"{topic} alternatives"),
    ]

    findings: list[str] = []
    for tool, query in plan:
        try:
            findings.append(await rt.call(tool, query=query))
        except MaxCallsExceededError as exc:
            findings.append(f"skipped {query!r}: {exc}")
    return findings


flow = rt.Flow("Max Calls Quickstart", entry_point=research)
# --8<-- [end: flow]


# --8<-- [start: first_run]
for line in flow.invoke(topic="mechanical keyboards"):
    print(line)

# Readable once the run is over, so you can log what it actually spent.
print(f"spent: {search_budget.call_count}/{search_budget.max_calls}")
# --8<-- [end: first_run]


# --8<-- [start: second_run]
# Each invoke() opens its own session, so the budget starts over.
for line in flow.invoke(topic="ergonomic mice"):
    print(line)

print(f"spent: {search_budget.call_count}/{search_budget.max_calls}")
# --8<-- [end: second_run]
