import pytest
from railtracks.built_nodes.concrete.response import StringResponse
from railtracks.exceptions.errors import NodeCreationError
from railtracks.llm.providers import ModelProvider
from .llm_map import llm_map
import railtracks as rt
from pydantic import BaseModel, Field
from typing import Optional, final

@pytest.mark.asyncio
@pytest.mark.parametrize("llm", llm_map.values(), ids=llm_map.keys())
async def test_function_as_tool(llm):
    """Test that a function with a single tool call works correctly."""

    def magic_number(input_num: int):
        """
        Args:
            input_num (int): The input number to test.
        """
        rt.context.put("magic_number_called", True)
        return input_num + 2
    
    def magic_operator(x: int, y: int = 3):
        """
        Args:
            x (int): The first number
            y (Optional[int]): The second number
        """
        rt.context.put("magic_operator_called", True)
        return (2 * x) + y
    
    agent = rt.agent_node(
        tool_nodes={rt.function_node(magic_number), rt.function_node(magic_operator)},
        name="Magic Number Agent",
        system_message="You are a helpful assistant that can call the tools available to you to answer user queries",
        llm=llm,
    )

    with rt.Session(logging_setting="NONE"):
        if llm.stream and llm.model_type() != ModelProvider.OPENAI:
            with pytest.raises(NodeCreationError):
                response = await rt.call(agent, user_input="First find the magic number for 4. Then use the magic_operator with `x` as the result from magic_number and `y` as 3. Return the result from the magic_operator.")

            return
        else:
            response = await rt.call(agent, user_input="First find the magic number for 4. Then use the magic_operator with `x` as the result from magic_number and `y` as 3. Return the result from the magic_operator.")

        final_resp = None
        if llm.stream:
            for chunk in response:
                assert isinstance(chunk, (str, StringResponse))
                if isinstance(chunk, StringResponse):
                    final_resp = chunk
        else:
            final_resp = response

        assert final_resp is not None
        assert '15' in final_resp.content
        assert rt.context.get("magic_number_called")
        assert rt.context.get("magic_operator_called")

@pytest.mark.asyncio
@pytest.mark.parametrize("llm", llm_map.values(), ids=llm_map.keys())
async def test_realistic_scenario(llm):
    """Test that a function with a realistic scenario works correctly."""

    class StaffDirectory(BaseModel):
        name: str = Field(description="The name of the staff member")
        role: str = Field(description="The role of the staff member")
        phone: str = Field(description="The phone number of the staff member")

    # Define DB at class level so it's accessible for assertions
    DB = {
        "John": {"role": "Manager", "phone": "1234567890"},
    }

    @rt.function_node
    def update_staff_directory(staff: list[StaffDirectory]) -> None:
        """
        For a given list of staff, updates the staff directory with new members or updates existing members.

        Args:
            staff (List[StaffDirectory]): The list of staff to to gather information about.

        """
        rt.context.put("staff_directory_updated", True)
        for person in staff:
            DB[person.name] = {"role": person.role, "phone": person.phone}

    usr_prompt = (
        "Update the staff directory with the following information: John is now a 'Senior Manager' and his phone number is changed to 5555"
        " and Jane is new a Developer and her phone number is 0987654321."
    )

    agent = rt.agent_node(
        tool_nodes={update_staff_directory},
        name="Staff Directory Agent",
        system_message="You are a helpful assistant that can call the tools available to you to answer user queries",
        llm=llm,
    )

    with rt.Session(logging_setting="NONE"):
        if llm.stream and llm.model_type() != ModelProvider.OPENAI:
            return
        else:
            response = await rt.call(
                agent, rt.llm.MessageHistory([rt.llm.UserMessage(usr_prompt)])
            )
        assert rt.context.get("staff_directory_updated")

        if llm.stream:
            for chunk in response:
                assert isinstance(chunk, (str, StringResponse))
                pass


    assert DB["John"]["role"] == "Senior Manager"
    assert DB["John"]["phone"] == "5555"
    assert DB["Jane"]["role"] == "Developer"
    assert DB["Jane"]["phone"] == "0987654321"

@pytest.mark.asyncio
@pytest.mark.parametrize("llm", llm_map.values(), ids=llm_map.keys())
async def test_agents_as_tools(llm):
    """Test that an agent using other agnets as tools works correctly."""

    @rt.function_node
    def secret_phrase(id: int):
        """
        Returns a secret phrase based on the id.
        Args:
            id (int): The id of the secret phrase to return.
        """
        rt.context.put("secret_phrase_called", True)
        secret_phrases = {
            0: "2 foxes and a dog",
            1: "3 cats and a dog",
            2: "4 foxes and a cat",
        }
        return secret_phrases[id]

    # Define the child tool
    child_tool = rt.agent_node(
        name="Secret Phrase Maker",
        system_message=rt.llm.SystemMessage("When asked for a response, procide the secret phrase for `secret_phrase_id`"),
        tool_nodes={rt.function_node(secret_phrase)},
        manifest=rt.ToolManifest(
            description="A tool that generates secret phrases.",
            parameters=[
                rt.llm.Parameter(
                    name="secret_phrase_id",
                    param_type="integer",
                    description="A numberic id of the secret phrase to return.",
                )
            ]
        ),
        llm=llm,
    )

    # Define the parent tool that uses the child tool
    parent_tool = rt.agent_node(
        tool_nodes={child_tool},
        name="Secrets Manager",
        system_message=rt.llm.SystemMessage(
            "You are a helpful assistant that can call the tools available to you to answer user queries"
        ),
        llm=llm,
    )

    # Run the parent tool
    with rt.Session(
        logging_setting="NONE", timeout=100
    ):
        if llm.stream and llm.model_type() != ModelProvider.OPENAI:
            return
        
        response = await rt.call(
            parent_tool, user_input="Get me the secret phrase for id `1`."
        )

        final_resp = None
        if llm.stream:
            for chunk in response:
                assert isinstance(chunk, (str, StringResponse))
                if isinstance(chunk, StringResponse):
                    final_resp = chunk
        else:
            final_resp = response
            
        assert final_resp is not None
        assert rt.context.get("secret_phrase_called")

    assert final_resp is not None
    assert "3 cats and a dog" in final_resp.content
    assert any(message.role == "tool" and message.content.name == "Secret_Phrase_Maker" for message in final_resp.message_history)    # child tool giving the secret phrase to parent

