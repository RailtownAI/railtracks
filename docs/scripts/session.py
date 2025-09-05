import asyncio
import railtracks as rt


# --8<-- [start: empty_session_dec]
@rt.function_node
async def greet(name: str) -> str:
    return f"Hello, {name}!"


@rt.session()
async def empty_workflow():
    result = await rt.call(greet, name="Alice")
    return result


# Run your workflow
result, session = asyncio.run(empty_workflow())
print(result)  # "Hello, Alice!"
print(f"Session ID: {session._identifier}")
# --8<-- [end: empty_session_dec]


# --8<-- [start: configured_session_dec]
@rt.session(
    timeout=30,  # 30 second timeout
    context={"user_id": "123"},  # Global context variables
    logging_setting="QUIET",  # Enable debug logging
    save_state=True,  # Save execution state to file
    name="my-unique-run",  # Custom session name
)
async def configured_workflow():
    result1 = await rt.call(greet, name="Bob")
    result2 = await rt.call(greet, name="Charlie")
    return [result1, result2]


result, session = asyncio.run(configured_workflow())
print(result)  # ['Hello, Bob!', 'Hello, Charlie!']
print(f"Session ID: {session._identifier}")
# --8<-- [end: configured_session_dec]


# --8<-- [start: multiple_sessions_dec]
@rt.function_node
async def farewell(name: str) -> str:
    return f"Bye, {name}!"


@rt.session(context={"action": "greet", "name": "Diana"}, logging_setting="QUIET")
async def first_workflow():
    if rt.context.get("action") == "greet":
        return await rt.call(greet, rt.context.get("name"))


@rt.session(context={"action": "farewell", "name": "Robert"}, logging_setting="QUIET")
async def second_workflow():
    if rt.context.get("action") == "farewell":
        return await rt.call(farewell, rt.context.get("name"))


# Run independently
result1, session1 = asyncio.run(first_workflow())
result2, _ = asyncio.run(second_workflow()) # if we don't want to work with Session Object
print(result1)  # "Hello, Diana!"
print(result2)  # "Bye, Robert!"
# --8<-- [end: multiple_sessions_dec]


# --8<-- [start: configured_session_cm]
async def context_workflow():
    with rt.Session(
        timeout=30,  # 30 second timeout
        context={"user_id": "123"},  # Global context variables
        logging_setting="QUIET",  # Enable debug logging
        save_state=True,  # Save execution state to file
        name="my-unique-run",  # Custom session name
    ):
        result1 = await rt.call(greet, name="Bob")
        result2 = await rt.call(greet, name="Charlie")
        return [result1, result2]


result = asyncio.run(context_workflow())
print(result)  # ['Hello, Bob!', 'Hello, Charlie!']
# --8<-- [end: configured_session_cm]


@rt.function_node
def sample_node():
    return "tool result"


# --8<-- [start: error_handling]
@rt.session(end_on_error=True)
async def safe_workflow():
    try:
        return await rt.call(sample_node)
    except Exception as e:
        print(f"Workflow failed: {e}")
        return None


# --8<-- [end: error_handling]


# --8<-- [start: api_example]
@rt.session(context={"api_key": "secret", "region": "us-west"})
async def api_workflow():
    # Context variables are available to all nodes
    result = await rt.call(sample_node)
    return result


# --8<-- [end: api_example]


# --8<-- [start: tracked]
@rt.session(save_state=True, name="daily-report-v1")
async def daily_report():
    # Execution state saved to .railtracks/daily-report-v1.json
    return await rt.call(sample_node)


# --8<-- [end: tracked]
