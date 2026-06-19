import railtracks as rt
import asyncio

@rt.function_node
def split_text(text: str) -> list[str]:
    return text.split()

# since the alternate_capitalization function is a simple operation, it can be a regular function
@rt.function_node
def alternate_capitalization(text: str) -> str:
    return text.swapcase()

# Since the modify_text function calls other nodes, it must be an async function
# You can use the asyncio library to run the nodes however you want.
@rt.function_node
async def modify_text(text: str) -> str:
    # Call the split_text node sequentially.
    words = await rt.call(split_text, text)

    # Process each word parallelly using asyncio.gather
    modified_words = await asyncio.gather(*(rt.call(alternate_capitalization, word) for word in words))

    # Join the modified words back into a single string
    return ' '.join(modified_words)