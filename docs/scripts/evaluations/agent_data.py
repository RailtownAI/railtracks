import railtracks as rt
from pydantic import BaseModel

# --8<-- [start: full_code]
class PhoneNumberResponse(BaseModel):
    first_name: str
    last_name: str
    phone_number: str

@rt.function_node
def directory(first_name: str, last_name: str) -> PhoneNumberResponse:
    """Returns the phone number for a given person
    
    Args:
        first_name: The person's first name
        last_name: The person's last name
    """

    phone_book = {
        ("John", "Doe"): "555-1234",
        ("Jane", "Smith"): "555-5678",
        ("Sam", "Brown"): "555-8765",
    }
    phone_number = phone_book.get((first_name, last_name), "Number not found")
    return PhoneNumberResponse(first_name=first_name, last_name=last_name, phone_number=phone_number)

@rt.function_node
def page_phone(phone_number: str):
    """Pages the given phone number.
    
    Args:
        phone_number: The phone number to call
    """
    return

DirectoryAgent = rt.agent_node(
    name="DirectoryAgent",
    system_message="You are a helpful agent that provides phone numbers from a directory.",
    llm=rt.llm.OpenAILLM(model_name="gpt-5"),
    tool_nodes=[directory, page_phone],
)
# --8<-- [start: agent_data]

@rt.session(name="Sample", save_data="io")
async def main() -> str:

    response = await rt.call(
        DirectoryAgent,
        "What is the phone number of Jane Smith and Sam Brown? Please page Sam once you have it.",

    )

    return response.content
# --8<-- [end: agent_data]
# --8<-- [end: full_code]

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())