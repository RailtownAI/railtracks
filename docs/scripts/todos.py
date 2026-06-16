# --8<-- [start: todos]
import railtracks as rt

# create your todo toolset
# optionally you can pass in a callback function that will be called every time a new todo is added.
to_dos = rt.prebuilt.ToDoToolSet(
    lambda short_desc, desc, state: print(f"Added todo: {short_desc} - {desc} [{state.value}]")
)

Agent = rt.agent_node(
    name="Test Agent",
    tool_nodes=[*to_dos.tool_set(), ], # this creates a list of tools your agent can access
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="..."
)
# --8<-- [end: todos]

# --8<-- [start: todo_prompt]
# the tool set contains a class method that returns a prompt to guide the agent in using the tool effectively.
rt.prebuilt.ToDoToolSet.prompt()
# --8<-- [start: todo_prompt]