import railtracks as rt

# --8<-- [start: callback_creation]
def example_broadcasting_handler(data):
    print(f"Received data: {data}")

rt.set_config(broadcast_callback=example_broadcasting_handler)
# --8<-- [end: callback_creation]

# --8<-- [start: broadcast_call]
@rt.function_node
async def example_node(data: list[str]):
    await rt.broadcast(f"Handling {len(data)} items")
# --8<-- [end: broadcast_call]




