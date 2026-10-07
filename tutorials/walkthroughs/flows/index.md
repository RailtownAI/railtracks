# Flows

Railtracks makes it easy to create custom agents with access to tools they can call to complete tasks. But what if you want to use agents themselves as tools? In this section, we’ll explore more complex flows and how Railtracks gives you control over them.

To start, let’s look at the simplest case: an agent that uses another agent as a tool.

### Example

```python
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


#As before, we will create our Weather Agent with the additional tool manifest so that other agents know how to use it
WeatherToolCallAgent = rt.agent_node(
    name="Weather Agent",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="You are a helpful assistant that answers weather-related questions.",
    tool_nodes=[rt.function_node(weather_tool)],
)

WeatherStructuredAgent = rt.agent_node(
    name="Weather Formatter Agent",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="Extract the temperature and condition from the assistant's answer.",
    output_schema=WeatherResponse,
)

#Call the ToolCall agent first, then hand its answer to the structured agent, wrapped by an rt function so it can be used as a tool
@rt.function_node
async def weather_agent(prompt: str):
    tool_response = await rt.call(WeatherToolCallAgent, user_input=prompt)
    return await rt.call(WeatherStructuredAgent, user_input=tool_response.content)



#Now lets create a hiking planner agent
HikingAgent = rt.agent_node(
    name="Hiking Agent",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="You are a helpful assistant that answers questions about which cities have the best conditions for hiking. The user should specify multiple cities near them.",
    tool_nodes=[weather_agent],
)
```

You can see here that the flow will look like this

```
graph LR
    A[Hiking Agent] --> B[Weather Agent]
    B --> C[Weather API]
    C --> B
    B --> A

    A -.->|"Calls for all cities"| B
```

## Another Simple Flow but Using Context to Ensure Precise Outputs

Specialized agents perform better than generalist ones. For the simplest of coding projects, you might use a Top Level Agent for ideation and dialogue, a Coding Agent for the code itself, and a Static Checker for validation. It would be important that once the Static Checker approves code, no agents modify it further though.

One important aspect of Railtracks is that it handles these complex flows through wrappers. All functions and flows can become nodes that you can run by wrapping them with `function_node`.

In the following example you'll see an example of how Railtracks deals with mid-flow validation.

### Example

```python
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
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
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

        valid, problem = static_check(response.content)

    with open("new_script.py", "w") as file:
        file.write(response.content)

    return "Success"

tool_nodes = {rt.function_node(code_agent, manifest=CodeManifest)}
CoordinatorAgent = rt.agent_node(
    system_message=CoordinatorMessage,
    tool_nodes=tool_nodes,
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    )

flow = rt.Flow("coordinator-flow", entry_point=CoordinatorAgent)
resp = flow.invoke("Would you be able to generate me code that takes 2 numbers as input and returns the sum?")
print(resp)
```

### What this flow would look like

```
graph TD
    Coordinator -->|1| CodeAgentWrapper["Code Agent Wrapper"]
    CodeAgentWrapper -->|2| CodeAgent["Code Agent"]
    CodeAgent -->|3| StaticCheck["Static Check"]
    StaticCheck -->|4| C{"Valid?"}
    C -->|No| CodeAgent
    C -->|Yes| D["Write To File"]
    D --> CodeAgentWrapper
    CodeAgentWrapper -->|5| Coordinator
```

Structuring Flows

When possible, you should try to keep your flows linear. Notice above that it would also be possible to give the coordinator access to both the static checker as well as the coding agent. In such a simple example, likely this would have been fine but two problems arise with this approach. Firstly, this is a simple validation step that should happen every time code is generated. Leaving it up to the coordinator to call the static checker adds unnecessary complexity to the agent and creates the possibility for the the validation step to be skipped. It can sometimes be easier to think about a more flexible flow but you try to linearize your flow as much as possible. The second problem we will discuss below.

## Handling More Complex Flows

While `function_node` works well for linear flows, some scenarios require transferring between different agents like moving from technical support to billing in a customer service system. In these cases, you need to pass data directly between agents without mutations or the "telephone game" effect of traditional handoffs. Railtracks solves this with [context](https://docs.railtracks.org/documentation/advanced/context/index.md), a mechanism for sharing data across agent transfers while preserving integrity. Let's see how context enables reliable multi-agent workflows.

### Customer Service Agents

```python
#Initialize all your system messages, schemas, and tools here.

QualityAssuranceAgent = rt.agent_node(
    name="Quality Assurance Agent",
    output_schema=StructuredResponse,
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    #adding all other arguments as needed
    )

ProductExpertAgent = rt.agent_node(
    name="Product Expert Agent",
    output_schema=StructuredResponse,
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    #adding all other arguments as needed
    )

BillingAgent = rt.agent_node(
    name="Billing Agent",
    output_schema=StructuredResponse,
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    #adding all other arguments as needed
    )

TechnicalAgent = rt.agent_node(
    name="Technical Support Agent",
    output_schema=StructuredResponse,
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
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
        new = previous + response.content.info
    else:
        new = response.content.info
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
        new = previous + response.content.info
    else:
        new = response.content.info
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
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message=CoordinatorMessage,
)


coordinator_flow = rt.Flow("coordinator-flow", entry_point=Coordinator)
coordinator_flow.invoke("I am having an issue with my product. I think it might be a billing issue but I am not sure. Can you help me figure out what is going on?")
```

### What an example flow would look like

```
graph TD
    Coordinator["Coordinator"] -->|1| Technical["Technical Support Agent"]
    Technical --> |2| Tools["Tool Calls"]
    Tools --> |3| Technical
    Technical --> |Puts| Context["Context"]
    Technical --> |4| Coordinator["Coordinator"]
    Coordinator -->|5| Billing["Billing Agent"]
    Context --> |Gets| Billing
    Billing --> |6| BillingTools["Tool Calls"]
    BillingTools --> |7| Billing
    Billing --> |8| Coordinator
```
