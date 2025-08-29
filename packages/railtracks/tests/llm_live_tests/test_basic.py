import pytest 
import railtracks as rt
from pydantic import BaseModel, Field
from .llm_map import llm_map

class Address(BaseModel):
    city: str = Field(description="The city the person lives in")
    country: str = Field(description="The country the person lives in")

class SimplePerson(BaseModel):
    name: str = Field(description="The name of the person")
    age: int = Field(description="The age of the person")

class ComplexPerson(BaseModel):
    name: str = Field(description="The name of the person")
    age: int = Field(description="The age of the person")
    address: Address = Field(description="The address info of the person")

# Test cases with schema, user input, and validation function
test_cases = [
    {
        "schema": SimplePerson,
        "user_input": "My name is Railtown and I am 6 years old. Please give me a structured response.",
        "validator": lambda response: (
            response.content.name == "Railtown" and 
            response.content.age == 6
        ),
        "case_id": "simple_person"
    },
    {
        "schema": ComplexPerson,
        "user_input": "My name is Alice and I am 25 years old. I live in Vancouver, Canada. Please give me a structured response.",
        "validator": lambda response: (
            response.content.name == "Alice" and 
            response.content.age == 25 and
            response.content.address.city == "Vancouver" and
            response.content.address.country == "Canada"
        ),
        "case_id": "complex_person"
    }
]

@pytest.mark.skip(reason="Skipped due to LLM stochasticity")
@pytest.mark.asyncio
@pytest.mark.parametrize("llm", llm_map.values(), ids=llm_map.keys())
async def test_terminal_llm(llm):
    """Test that a basic terminal llm can be created and used."""

    terminal_node = rt.agent_node(
        name="Terminal Node",
        system_message="You are a helpful assistant reverses the input string.",
        llm=llm,
    )

    with rt.Session(logging_setting="NONE"):
        response = await rt.call(
            terminal_node, user_input="Please reverse '12345'."
        )

        assert '54321' in response.content

@pytest.mark.skip(reason="Skipped due to LLM stochasticity")
@pytest.mark.asyncio
@pytest.mark.parametrize("llm", llm_map.values(), ids=llm_map.keys())
@pytest.mark.parametrize("test_case", test_cases, ids=[case["case_id"] for case in test_cases])
async def test_structured_llm(llm, test_case):
    """Test that structured LLMs work with various schema types."""
    
    structured_node = rt.agent_node(
        output_schema=test_case["schema"],
        name="Structured Node",
        system_message="You are a helpful assistant that extracts information into structured format.",
        llm=llm,
    )

    with rt.Session(logging_setting="NONE"):
        response = await rt.call(
            structured_node, 
            user_input=test_case["user_input"]
        )

        # Basic type check
        assert isinstance(response.content, test_case["schema"])
        
        # Custom validation
        assert test_case["validator"](response), f"Validation failed for {test_case['case_id']}"
