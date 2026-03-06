import railtracks as rt


# --8<-- [start: empty_session_dec]
@rt.function_node
async def greet(name: str) -> str:
    return f"Hello, {name}!"


flow = rt.Flow("greet-flow", entry_point=greet)
result = flow.invoke(name="Alice")
print(result)  # "Hello, Alice!"
# --8<-- [end: empty_session_dec]


# --8<-- [start: configured_session_dec]
@rt.function_node
async def greet_multiple(names: list[str]):
    results = []
    for name in names:
        result = await rt.call(greet, name=name)
        results.append(result)
    return results

greeting_multiple_flow = rt.Flow(
    "greet-multiple-flow",
    entry_point=greet_multiple,
    timeout=30,  # 30 second timeout
    context={"user_id": "123"},  # Global context variables
    logging_setting="DEBUG",  # Enable debug logging
    save_state=True,  # Save execution state to file
)

multiple_greeting_response = greeting_multiple_flow.invoke(names=["Bob", "Charlie"])
print(multiple_greeting_response)  # ['Hello, Bob!', 'Hello, Charlie!']
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
    "greet-flow",
    entry_point=conditional_greet,
    context={"action": "greet", "name": "Diana"},
    logging_setting="CRITICAL"
)

second_flow = rt.Flow(
    "farewell-flow",
    entry_point=conditional_farewell,
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
second_flow = rt.Flow(
    "greet-multiple-flow",
    entry_point=greet_multiple,
    timeout=30,  # 30 second timeout
    context={"user_id": "123"},  # Global context variables
    logging_setting="DEBUG",  # Enable debug logging
    save_state=True,  # Save execution state to file
)

result = second_flow.invoke(names =["Bob", "Charlie"])
print(result)  # ['Hello, Bob!', 'Hello, Charlie!']
# --8<-- [end: configured_session_cm]


@rt.function_node
def sample_node():
    return "tool result"


# --8<-- [start: error_handling]
sample_node_flow = rt.Flow("sample-flow", entry_point=sample_node, end_on_error=True)
try:
    result = sample_node_flow.invoke()
except Exception as e:
    print(f"Flow failed: {e}")

# --8<-- [end: error_handling]


# --8<-- [start: api_example]
sample_node_flow = rt.Flow("api-flow", entry_point=sample_node, context={"api_key": "secret", "region": "us-west"})
# Context variables are available to all nodes
result = sample_node_flow.invoke()

# --8<-- [end: api_example]


# --8<-- [start: tracked]
sample_node_flow = rt.Flow("daily-report-v1", entry_point=sample_node, save_state=True)
# Execution state saved to .railtracks/daily-report-v1.json
result = sample_node_flow.invoke()

# --8<-- [end: tracked]
