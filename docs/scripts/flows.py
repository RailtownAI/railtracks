# --8<-- [start: imports]
import railtracks as rt
from pydantic import BaseModel
# --8<-- [end: imports]

# --8<-- [start: weather_response]
class WeatherResponse(BaseModel):
    temperature: float
    condition: str
# --8<-- [end: weather_response]

# --8<-- [start: weather_tool]
def weather_tool(city: str):
    """
    Returns the current weather for a given city.

    Args:
      city (str): The name of the city to get the weather for.
    """
    # Simulate a weather API call
    return f"{city} is sunny with a temperature of 25°C."
# --8<-- [end: weather_tool]

 
# --8<-- [start: weather_manifest]
weather_manifest = rt.ToolManifest(
description="A tool you can call to see what the weather in a specified city",
    parameters=[rt.llm.Parameter("prompt", "string", "Specify the city you want to know about here")]
)
# --8<-- [end: weather_manifest]

# --8<-- [start: weather_tool]
WeatherAgent = rt.agent_node(
    name="Weather Agent",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful assistant that answers weather-related questions.",
    tool_nodes=[rt.function_node(weather_tool)],
    output_schema=WeatherResponse,
    manifest=weather_manifest
)
# --8<-- [end: weather_tool]

# --8<-- [start: HikingAgent]
HikingAgent = rt.agent_node(
    name="Hiking Agent",
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message="You are a helpful assistant that answers questions about which cities have the best conditions for hiking. The user should specify multiple cities near them.",
    tool_nodes=[WeatherAgent],
)
# --8<-- [end: HikingAgent]

# --8<-- [start: coding_imports]
import railtracks as rt
import ast
# --8<-- [end: coding_imports]

# --8<-- [start: static_check]
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
# --8<-- [end: static_check]

# --8<-- [start: CodeManifest]    
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
# --8<-- [end: CodeManifest]

# --8<-- [start: CodingMessage]
CodingMessage = """You are a master python agent that helps users by 
providing elite python code for their requests. You will output valid python code that can be directly used without any further editing. Do not add anything other than the python code and python comments if you see fit."""

CoordinatorMessage = """You are a helpful assistant that will talk to users about the type of code they want. You have access to a CodeAgent tool to generate the code the user is looking for. Your job is to clarify with users to ensure that they have provided all details required to write the code and then effectively communicate that to the CodeAgent. Do not write any code and strictly refer to the CodeAgent for this."""
# --8<-- [end: CodingMessage]

# --8<-- [start: CodeAgent]
#Create our Coding Agent as usual
coding_agent = rt.agent_node(
    name="Code Tool",
    system_message=CodingMessage,
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    )
# --8<-- [end: CodeAgent]

# --8<-- [start: CodeWrapper]
#Wrap our Validation and file writing flow in a function
def CodeAgent(title : str, prompt : str):
    valid = False
    problem = "There were no problems last time"
    while not valid:
        response = rt.call_sync(
        coding_agent,
        user_input=prompt + " Your Problem Last Time: " + problem
        )

        valid, problem = static_check(response.text)

    with open("new_script.py", "w") as file:
        file.write(response.text)
    
    return "Success"
# --8<-- [end: CodeWrapper]

# --8<-- [start: CodeCoordinatorAgent]
tool_nodes = {rt.function_node(CodeAgent, tool_manifest=CodeManifest)}
CoordinatorAgent = rt.chatui_node(
    system_message=CoordinatorMessage,
    tool_nodes=tool_nodes,
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    )
# --8<-- [end: CodeCoordinatorAgent]

# --8<-- [start: call_code_coordinator]
rt.call_sync(
        CoordinatorAgent,
        user_input="Would you be able to generate me code that takes 2 numbers as input and returns the sum?"
    )
# --8<-- [end: call_code_coordinator]

# --8<-- [start: customer_imports]
import railtracks as rt
# --8<-- [end: customer_imports]

# --8<-- [start: customer_agents]
#Initialize all your system messages, schemas, and tools here.
...

QualityAssuranceAgent = rt.agent_node(
    name="Quality Assurance Agent",
    #adding all other arguments as needed
    )

ProductExpertAgent = rt.agent_node(
    name="Product Expert Agent",
    #adding all other arguments as needed
    )

BillingAgent = rt.agent_node(
    name="Billing Agent",
    #adding all other arguments as needed
    )
    
TechnicalAgent = rt.agent_node(
    name="Technical Support Agent",
    #adding all other arguments as needed
    )
# --8<-- [end: customer_agents]

# --8<-- [start: BillingTool]
def BillingTool(prompt : str):
    try:
        prompt = prompt + "Previously the User had this interaction " + rt.context.get("info_from_other_agents")
        has_context = True
    except KeyError:
        has_context = False
    response = rt.call_sync(
        BillingAgent,
        user_input=prompt
        )
    if has_context:
        previous = rt.context.get("info_from_other_agents")
        new = previous + response.structured.info
    else:
        new = response.structured.info
    rt.context.put("info_from_other_agents", new)
# --8<-- [end: BillingTool]

# --8<-- [start: TechnicalTool]
def TechnicalTool(prompt : str):
    try:
        prompt = prompt + "Previously the User had this interaction " + rt.context.get("info_from_other_agents")
        has_context = True
    except KeyError:
        has_context = False
    response = rt.call_sync(
        TechnicalAgent,
        user_input=prompt
        )
    if has_context:
        previous = rt.context.get("info_from_other_agents")
        new = previous + response.structured.info
    else:
        new = response.structured.info
    rt.context.put("info_from_other_agents", new)
# --8<-- [end: TechnicalTool]

# --8<-- [start: OtherTools]
#This would be similar to functions above
def QATool():
    ...
#This would be similar to functions above
def PETool():
    ...
# --8<-- [end: OtherTools]

# --8<-- [start: CustomerCoordinatorAgent]
tools = {rt.function_node(BillingTool), rt.function_node(TechnicalTool), rt.function_node(QATool), rt.function_node(PETool)}

Coordinator = rt.agent_node(
    name="Coordinator Agent",
    tool_nodes=tools,
    llm_model=rt.llm.OpenAILLM("gpt-4o"),
    system_message=CoordinatorMessage,
)

response = rt.call_sync(
        CoordinatorAgent,
        user_input=""
    )
# --8<-- [end: CustomerCoordinatorAgent]