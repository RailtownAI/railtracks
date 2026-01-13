While the interactions of your agents are automatically saved by the backend to be used by the visualizer in `.railtracks/data/sessions/`, these files are meant to be directly utilized by using the local visualizer. We also know the value of having **_human readable_** files.

For this reason we introduced the concept of **`AgentDataPoint`** where the user can request the backend to provide human readable files located in `railtracks/data/agent_data`. This is done by simply passing one of the values below to the parameter **`save_data`**:

1. `"io"`: The default setting
2. `"full"`: Records internal agent tool invocations
3. `"none"`: Data will not be saved.
```python
--8<-- "docs/scripts/evaluations/agent_data.py:agent_data"
```

???+ note "File Naming"
    If you provide your session with a name, this name is prefixed to the filename for the agent data, ie `Function_dd91864e-bd72-474c-8ce9-d777f8b9b5f9.json`. The reason the _identifier_ is kept as part of the name is for agent files to not be written over after the user rerunning the same script.

???+ note "`"io"` output for the above script"
    ```json
    [
    {
        "agent_name": "DirectoryAgent",
        "agent_input": {
        "args": [
            "What is the phone number of Jane Smith and Sam Brown? Please page Sam once you have it."
        ],
        "kwargs": {}
        },
        "agent_output": "Here are the numbers:\n- Jane Smith: 555-5678\n- Sam Brown: 555-8765\n\nI\u2019ve paged Sam at 555-8765.",
        "agent_internals": null
    }
    ]
    ```
??? note "`"full"` output for the above script"
    ```json
        [
        {
            "agent_name": "DirectoryAgent",
            "agent_input": {
            "args": [
                "What is the phone number of Jane Smith and Sam Brown? Please page Sam once you have it."
            ],
            "kwargs": {}
            },
            "agent_output": "Here are the numbers:\n- Jane Smith: 555-5678\n- Sam Brown: 555-8765\n\nI\u2019ve paged Sam at 555-8765.",
            "agent_internals": {
            "run_id": "2b6c8a68-3f30-4195-a872-c14ca8c09799",
            "message_history": [
                {
                "role": "user",
                "content": "What is the phone number of Jane Smith and Sam Brown? Please page Sam once you have it."
                },
                {
                "role": "assistant",
                "content": "[ToolCall(identifier='call_wa2sTXGZyVIeKHr30CSl9TYo', name='directory', arguments={'first_name': 'Jane', 'last_name': 'Smith'}), ToolCall(identifier='call_7GXkMLm61xthaAr3Z6tfkKTr', name='directory', arguments={'first_name': 'Sam', 'last_name': 'Brown'})]"
                },
                {
                "role": "tool",
                "content": "directory -> first_name='Jane' last_name='Smith' phone_number='555-5678'"
                },
                {
                "role": "tool",
                "content": "directory -> first_name='Sam' last_name='Brown' phone_number='555-8765'"
                },
                {
                "role": "assistant",
                "content": "[ToolCall(identifier='call_LUciFyteQP42Q80JAWFIdcPN', name='page_phone', arguments={'phone_number': '555-8765'})]"
                },
                {
                "role": "tool",
                "content": "page_phone -> None"
                },
                {
                "role": "assistant",
                "content": "Here are the numbers:\n- Jane Smith: 555-5678\n- Sam Brown: 555-8765\n\nI\u2019ve paged Sam at 555-8765."
                }
            ],
            "tool_invocations": [
                {
                "name": "directory",
                "arguments": {
                    "first_name": "Jane",
                    "last_name": "Smith"
                },
                "result": "first_name='Jane' last_name='Smith' phone_number='555-5678'"
                },
                {
                "name": "directory",
                "arguments": {
                    "first_name": "Sam",
                    "last_name": "Brown"
                },
                "result": "first_name='Sam' last_name='Brown' phone_number='555-8765'"
                },
                {
                "name": "page_phone",
                "arguments": {
                    "phone_number": "555-8765"
                },
                "result": "None"
                }
            ]
            }
        }
        ]
    
    ```

??? note "Full script for the example above"
    ```python
    --8<-- "docs/scripts/evaluations/agent_data.py"
    ```