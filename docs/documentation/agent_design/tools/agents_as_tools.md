We support using agents as tools in the following two ways:

## 1. Python Function
By using a python function to call your agent, you can have the flexibility of your agent being invoked in different ways in different contexts. You will then simply [pass this function as a tool]() to your Orchestrator.
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

## 2. Agent Manifest
In this way, at agent definition time, you also define how this agent can be used by other agents.
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

You can refer to [API Reference](../../../api_reference/railtracks.html) for more information. Or take a look at our [Tutorials]() section.