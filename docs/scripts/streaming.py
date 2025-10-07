# --8<-- [start: streaming_flag]
from typing import Generator
from railtracks.built_nodes.concrete.response import LLMResponse
import railtracks.llm as llm
from railtracks.llm.response import Response 

model = llm.OpenAILLM(model_name="gpt-4o", stream=True)
# --8<-- [end: streaming_flag]


# --8<-- [start: streaming_usage]
model = llm.OpenAILLM(model_name="gpt-4o", stream=True)

response = model.chat(llm.MessageHistory([
    llm.UserMessage("Tell me who you are are"),
]))

# The response object can act as an iterator returning string chunks terminating with the complete message.
if isinstance(response, Generator):
    for chunk in response:
        print(chunk)
# --8<-- [end: streaming_usage]

# --8<-- [start: streaming_with_agents]
import railtracks as rt

agent = rt.agent_node(
    llm=rt.llm.OpenAILLM(model_name="gpt-4o", stream=True),
)

# --8<-- [end: streaming_with_agents]


# --8<-- [start: streaming_agent_usage]
agent = rt.agent_node(
    llm=rt.llm.OpenAILLM(model_name="gpt-4o", stream=True),
)

@rt.session
async def main():
    result = await rt.call(agent, rt.llm.MessageHistory([
        rt.llm.UserMessage("Tell me who you are are"),
        ]))
    
    # The response object can act as an iterator returning string chunks terminating with the complete message.
    if isinstance(result, Generator): 
        for chunk in result:
            print(chunk)
    
    

# --8<-- [end: streaming_agent_usage]
