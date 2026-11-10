# --8<-- [start: echo]
import railtracks as rt

agent = rt.agent_node(
    llm=rt.llm.EchoLLM(),
    system_message="You are a helper",
)

flow = rt.Flow("Echo example", entry_point=agent)
result = flow.invoke("hi")
print(result.content)
# --8<-- [end: echo]
