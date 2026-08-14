# --8<-- [start: todos]
import railtracks as rt

# optionally you can pass in a callback function that will be called every time a new todo is added.
def callback(short_description: str, description: str, state):
    print(f"Agent planned task: [{state.value}] {short_description} - {description}")

# create your todo toolset
to_dos = rt.prebuilt.ToDoToolSet(
    callback=callback
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
# --8<-- [end: todo_prompt]

# --8<-- [start: todo_callback]
import railtracks as rt

completed_tasks: list[str] = []

def on_todo_added(short_description: str, description: str, state):
    # called once per add() — use this to update a UI, write to a DB, send a notification, etc.
    print(f"Agent planned task: [{state.value}] {short_description} - {description}")
    completed_tasks.append(short_description)

to_dos = rt.prebuilt.ToDoToolSet(callback=on_todo_added)

agent = rt.agent_node(
    name="Report Agent",
    tool_nodes=[*to_dos.tool_set()],
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message=rt.prebuilt.ToDoToolSet.prompt() + "\nGenerate a monthly sales report.",
)
# --8<-- [end: todo_callback]

# --8<-- [start: todo_inspection]
# inspect the todo list after the agent run completes
print(to_dos.pretty_dashboard())
# To-Dos
# completed - fetch_data
# completed - clean_data
# completed - generate_report

incomplete = to_dos.get_incomplete_todos()
if incomplete:
    raise RuntimeError(f"Agent left tasks unfinished: {incomplete}")
# --8<-- [end: todo_inspection]
