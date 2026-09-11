We support using agents as tools in the following two ways:

## 1. Python Function
By using a python function to call your agent, you can have the flexibility of your agent being invoked in different ways in different contexts. You will then simply [pass this function as a tool](function_tools.md) to your Orchestrator.
```python
import railtracks as rt
from my_agents import SomeAgent

@rt.function_node
def some_way(arg1: arg1_type, arg2: arg2_type) -> return_type
    """Here you can tell the Orchestrator what this agent/tool does

    Args:
        arg1: ...
        arg2: ....
    """
    ...
```

## 2. Tool Manifest
A **tool manifest** is the description an agent carries of how other agents may call it: a description of what it does and the parameters it expects. Passing `manifest=` at agent definition time means any other agent can take this one as a tool without a wrapper function.
```python
import railtracks as rt

WorkerAgent = rt.agent_node(
    ...
    manifest=rt.ToolManifest(
        description="Telling Agents using this agent what it does",
        parameters=[
            rt.llm.Parameter(
                name="param_name",
                description="definition of parameter",
                param_type="param_type",
            ),
        ],
    ),
)
```

You can refer to [API Reference](../../../api_reference/railtracks.html) for more information. Or take a look at the [Agents as Tools](../../../tutorials/walkthroughs/agents_as_tools.md) walkthrough.