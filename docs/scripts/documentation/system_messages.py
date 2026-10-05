# --8<-- [start: two_sources]
import railtracks as rt

# Configuration: sent on every call to this agent.
Assistant = rt.agent_node(
    "Assistant",
    llm=rt.llm.OpenAILLM("gpt-6-luna"),
    system_message="You are terse.",
)

# Conversation: part of the history the caller owns.
history = rt.llm.MessageHistory(
    [
        rt.llm.SystemMessage("Var A = 123"),
        rt.llm.UserMessage("What is Var A?"),
    ]
)
# --8<-- [end: two_sources]

# --8<-- [start: next_turn]
response = await rt.call(Assistant, history)

next_turn = response.message_history
next_turn.append(rt.llm.UserMessage("And Var B?"))

response = await rt.call(Assistant, next_turn)
# --8<-- [end: next_turn]
