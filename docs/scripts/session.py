import railtracks as rt


# --8<-- [start: empty_session_dec]
@rt.function_node
async def greet(name: str) -> str:
    return f"Hello, {name}!"


flow = rt.Flow(greet)
result = flow.invoke(name="Alice")
print(result)  # "Hello, Alice!"
# --8<-- [end: empty_session_dec]


# --8<-- [start: configured_session_dec]
@rt.function_node
async def greet_multiple(names: list[str]) -> list[str]:
    results = []
    for name in names:
        results.append(await rt.call(greet, name=name))
    return results

flow = rt.Flow(
    greet_multiple,
    timeout=30,  # 30 second timeout
    context={"user_id": "123"},  # Global context variables
    logging_setting="DEBUG",  # Enable debug logging
    save_state=True,  # Save execution state to file
    name="my-unique-run",  # Custom flow name
)

result = flow.invoke(names=["Bob", "Charlie"])
print(result)  # ['Hello, Bob!', 'Hello, Charlie!']
# --8<-- [end: configured_session_dec]


# --8<-- [start: multiple_sessions_dec]
@rt.function_node
async def farewell(name: str) -> str:
    return f"Bye, {name}!"

@rt.function_node
async def conditional_greet():
    if rt.context.get("action") == "greet":
        return await rt.call(greet, rt.context.get("name"))

@rt.function_node
async def conditional_farewell():
    if rt.context.get("action") == "farewell":
        return await rt.call(farewell, rt.context.get("name"))

# Create independent flows
first_flow = rt.Flow(
    conditional_greet,
    context={"action": "greet", "name": "Diana"},
    logging_setting="CRITICAL"
)

second_flow = rt.Flow(
    conditional_farewell,
    context={"action": "farewell", "name": "Robert"},
    logging_setting="CRITICAL"
)

# Run independently
result1 = first_flow.invoke()
result2 = second_flow.invoke()
print(result1)  # "Hello, Diana!"
print(result2)  # "Bye, Robert!"
# --8<-- [end: multiple_sessions_dec]


# --8<-- [start: configured_session_cm]
# Flow configuration approach (replaces session context manager)
flow = rt.Flow(
    greet_multiple,
    timeout=30,  # 30 second timeout
    context={"user_id": "123"},  # Global context variables
    logging_setting="DEBUG",  # Enable debug logging
    save_state=True,  # Save execution state to file
    name="my-unique-run",  # Custom flow name
)

result = flow.invoke(names=["Bob", "Charlie"])
print(result)  # ['Hello, Bob!', 'Hello, Charlie!']
# --8<-- [end: configured_session_cm]


@rt.function_node
def sample_node():
    return "tool result"


# --8<-- [start: error_handling]
flow = rt.Flow(sample_node, end_on_error=True)
try:
    result = flow.invoke()
except Exception as e:
    print(f"Flow failed: {e}")
    result = None

# --8<-- [end: error_handling]


# --8<-- [start: api_example]
flow = rt.Flow(sample_node, context={"api_key": "secret", "region": "us-west"})
# Context variables are available to all nodes
result = flow.invoke()

# --8<-- [end: api_example]


# --8<-- [start: tracked]
flow = rt.Flow(sample_node, save_state=True, name="daily-report-v1")
# Execution state saved to .railtracks/daily-report-v1.json
result = flow.invoke()

# --8<-- [end: tracked]
