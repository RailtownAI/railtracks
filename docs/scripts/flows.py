import asyncio
# --8<-- [start: hiking_example]
from distro import info
import railtracks as rt
from pydantic import BaseModel
 
class WeatherResponse(BaseModel):
    temperature: float
    condition: str

def weather_tool(city: str):
    """
    Returns the current weather for a given city.

    Args:
      city (str): The name of the city to get the weather for.
    """
    # Simulate a weather API call
    return f"{city} is sunny with a temperature of 25°C."

weather_manifest = rt.ToolManifest(
description="A tool you can call to see what the weather in a specified city",
    parameters=[rt.llm.Parameter("prompt", "string", "Specify the city you want to know about here")]
)

#As before, we will create our Weather Agent with the additional tool manifest so that other agents know how to use it
WeatherAgent = rt.agent_node(
    name="Weather Agent",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful assistant that answers weather-related questions.",
    tool_nodes=[rt.function_node(weather_tool)],
    output_schema=WeatherResponse,
    manifest=weather_manifest
)

#Now lets create a hiking planner agent
HikingAgent = rt.agent_node(
    name="Hiking Agent",
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful assistant that answers questions about which cities have the best conditions for hiking. The user should specify multiple cities near them.",
    tool_nodes=[WeatherAgent],
)
# --8<-- [end: hiking_example]

# --8<-- [start: coding_example]
import ast

#Static checking function
def static_check(code: str) -> tuple[bool, str]:
    """
    Checks the syntax validity of Python code stored in the variable `code`.

    Attempts to parse the code using Python's AST module. Returns a tuple indicating whether the syntax is valid and a message describing the result.

    Returns:
        tuple[bool, str]:
            - True and a success message if the syntax is valid.
            - False and an error message if a SyntaxError is encountered.
    """
    try:
        ast.parse(code)
        return True, "Syntax is valid"
    except SyntaxError as e:
        return False, f"Syntax error: {e}"
   
CodeManifest = rt.ToolManifest(
    """This is an agent that is an python coder and can write any
     code for you if you specify what you would like.""",
    set([rt.llm.Parameter(
        name='prompt',
        param_type='string',
        description="""This is the prompt that you should provide that 
        tells the CodeAgent what you would like to code.""",
        )])
    )

CodingMessage = """You are a master python agent that helps users by 
providing elite python code for their requests. You will output valid python code that can be directly used without any further editing. Do not add anything other than the python code and python comments if you see fit."""

CoordinatorMessage = """You are a helpful assistant that will talk to users about the type of code they want. You have access to a CodeAgent tool to generate the code the user is looking for. Your job is to clarify with users to ensure that they have provided all details required to write the code and then effectively communicate that to the CodeAgent. Do not write any code and strictly refer to the CodeAgent for this."""

#Create our Coding Agent as usual
CodingAgent = rt.agent_node(
    name="Code Tool",
    system_message=CodingMessage,
    llm=rt.llm.OpenAILLM("gpt-4o"),
    )

#Wrap our Validation and file writing flow in a function
async def code_agent(prompt : str):
    valid = False
    problem = "There were no problems last time"
    while not valid:
        response = await rt.call(
        CodingAgent,
        user_input=prompt + " Your Problem Last Time: " + problem
        )

        valid, problem = static_check(response.text)

    with open("new_script.py", "w") as file:
        file.write(response.text)
    
    return "Success"

tool_nodes = {rt.function_node(code_agent, manifest=CodeManifest)}
CoordinatorAgent = rt.agent_node(
    system_message=CoordinatorMessage,
    tool_nodes=tool_nodes,
    llm=rt.llm.OpenAILLM("gpt-4o"),
    )

async def run():
    resp = await rt.call(
            CoordinatorAgent,
            user_input="Would you be able to generate me code that takes 2 numbers as input and returns the sum?"
        )
    print(resp)
# --8<-- [end: coding_example]

class StructuredResponse(BaseModel):
    info: str
# --8<-- [start: customer_example]
#Initialize all your system messages, schemas, and tools here.

QualityAssuranceAgent = rt.agent_node(
    name="Quality Assurance Agent",
    output_schema=StructuredResponse,
    #adding all other arguments as needed
    )

ProductExpertAgent = rt.agent_node(
    name="Product Expert Agent",
    output_schema=StructuredResponse,
    #adding all other arguments as needed
    )

BillingAgent = rt.agent_node(
    name="Billing Agent",
    output_schema=StructuredResponse,
    #adding all other arguments as needed
    )
    
TechnicalAgent = rt.agent_node(
    name="Technical Support Agent",
    output_schema=StructuredResponse,
    #adding all other arguments as needed
    )

async def billing_tool(prompt : str):
    try:
        prompt = prompt + "Previously the User had this interaction " + rt.context.get("info_from_other_agents")
        has_context = True
    except KeyError:
        has_context = False
    response = await rt.call(
        BillingAgent,
        user_input=prompt
        )
    if has_context:
        previous = rt.context.get("info_from_other_agents")
        new = previous + response.structured.info
    else:
        new = response.structured.info
    rt.context.put("info_from_other_agents", new)

async def technical_tool(prompt : str):
    try:
        prompt = prompt + "Previously the User had this interaction " + rt.context.get("info_from_other_agents")
        has_context = True
    except KeyError:
        has_context = False
    response = await rt.call(
        TechnicalAgent,
        user_input=prompt
        )
    if has_context:
        previous = rt.context.get("info_from_other_agents")
        new = previous + response.structured.info
    else:
        new = response.structured.info
    rt.context.put("info_from_other_agents", new)

#This would be similar to functions above
def qa_tool():
    ...
#This would be similar to functions above
def pe_tool():
    ...

tools = {rt.function_node(billing_tool), rt.function_node(technical_tool), rt.function_node(qa_tool), rt.function_node(pe_tool)}

Coordinator = rt.agent_node(
    name="Coordinator Agent",
    tool_nodes=tools,
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message=CoordinatorMessage,
)

async def main():
    response = await rt.call(
            CoordinatorAgent,
            user_input=""
        )
# --8<-- [end: customer_example]