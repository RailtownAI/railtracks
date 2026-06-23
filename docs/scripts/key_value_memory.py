# --8<-- [start: kv_memory]
import railtracks as rt

# create your key-value memory toolset (defaults to an in-process store)
memory = rt.prebuilt.KeyValueMemoryToolSet()

agent = rt.agent_node(
    name="Memory Agent",
    tool_nodes=[*memory.tool_set()],  # the tools your agent can call
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message="...",
)
# --8<-- [end: kv_memory]

# --8<-- [start: kv_memory_prompt]
# the tool set provides a class method returning a prompt that guides the agent.
rt.prebuilt.KeyValueMemoryToolSet.prompt()
# --8<-- [end: kv_memory_prompt]

# --8<-- [start: kv_memory_persistent]
import railtracks as rt
from railtracks.retrieval.stores.key_value import InMemoryKeyValueStore

# pass a store with a snapshot_path to persist memory across runs
memory = rt.prebuilt.KeyValueMemoryToolSet(
    store=InMemoryKeyValueStore(snapshot_path="memory.json"),
)

agent = rt.agent_node(
    name="Memory Agent",
    tool_nodes=[*memory.tool_set()],
    llm=rt.llm.OpenAILLM("gpt-4o"),
    system_message=rt.prebuilt.KeyValueMemoryToolSet.prompt(),
)
# --8<-- [end: kv_memory_persistent]

# --8<-- [start: kv_memory_callback]
import railtracks as rt

# called after every save (value=<new value>) and forget (value=None) —
# use it to mirror memory to a UI, a database, or a log.
def on_change(key: str, value: str | None):
    if value is None:
        print(f"Agent forgot {key!r}")
    else:
        print(f"Agent remembered {key!r} = {value!r}")

memory = rt.prebuilt.KeyValueMemoryToolSet(on_change=on_change)
# --8<-- [end: kv_memory_callback]

# --8<-- [start: kv_memory_inspection]
# inspect memory directly at any point (the store is async)
import asyncio

print(asyncio.run(memory.store.items()))
# {"user_timezone": "PST", "project_deadline": "2026-07-01"}
# --8<-- [end: kv_memory_inspection]
