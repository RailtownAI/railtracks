# How to Customize Class Building

RailTracks `define_agent` allows user to configure agent classes with set parameters you can choose from. These parameters suffice for most cases but what if you want to make an agent with just slightly more functionality? RailTracks has you covered again! Using our NodeBuilder class you can create your own agent class with many of the same functionalities provided in `define_agent` but the option to add class methods and attributes of your choice. 

NodeBuilder is sort of the subway of agents, you get to choose what you do and don't want your nodes to have. This will be important to keep in mind as every line will be a choice changing the [node factory](link this) that you're building.

---

## Initializing NodeBuilder

To initialize your NodeBuilder you will first choose which node class you would like to inherit from. Currently we have Terminal, Structured, ToolCall, and StructuredToolCall as the most common classes to inherit from. If you need more complexity you will need to inherit from ancestors to the more common classes. This is not advised unless you are an expert in the framework, in which case would you like a job at Railtown.ai?
Once you have chosen the class to inherit from you will choose a name (helpful for debugging), a class name, and advanced parameters for if you would like certain results directly returned to context.

## Creating an LLM Node

Although most of the time you are going to be creating nodes that use an LLM, this is not required and you can use NodeBuilder to build a totally different node. This is not advised though as we have [function nodes](link this if we still call them this) which should be used instead. If you know about function nodes but choose to use NodeBuilder without calling `llm_base`, please consider applying at railtown.ai.

So the first method you will be calling is `llm_base` where you will specify the system message and the llm you would like the node to use.

## Choosing Functionality

As is the case with our agent_node function, you will be able to choose the tools, max tool calls allowed, the structure of the output, and tool details. As usual, all of these are not required, unless you inherit from a class that requires certain attributes.

## Building!

Finally, you can build your node using the build method and you have your first custom made node!

### Example of building a Structured Tool Call LLM

```python
builder = NodeBuilder[StructuredToolCallLLM[_TOutput]](
        StructuredToolCallLLM,
        name=name,
        class_name="EasyStructuredToolCallLLM",
        return_into=return_into,
        format_for_return=format_for_return,
        format_for_context=format_for_context,
    )

builder.llm_base(llm_model, system_message)
builder.tool_calling_llm(set(tool_nodes), max_tool_calls)
builder.tool_callable_llm(tool_details, tool_params)
builder.structured(output_schema)

node = builder.build()
```
---

## Advanced Usage

If you are an advanced user and would like to add further functionality to your node we have you covered!(Please apply to railtown.ai)
By using our `add_attribute` method, you can add class attributes and methods that are not currently covered by RailTracks.


```python


```


```python

#This is the add_attribute method we would have in NodeBuilder
def add_attribute(self, **kwargs):

        for key, val in kwargs.items():
            if callable(val):
                self._with_override(key, classmethod(val))
            else:
                self._with_override(key, val)
```


```python

#What our easywrapper classes would look like now
def anything_LLM_Base_Wrapper(
    name,
    ...
    return_onto_into_and_possibly_nearby_context,
    **kwargs
):
    builder = NodeBuilder(...)
    ...
    add_attribute(**kwargs) #We add this one line to all classes. Maybe put in build() to help DRY
    builder.build()
```

```python

#What using this would look like with one_wrapper
def chat_ui(
        self,
        chat_ui: ChatUI,
    ):
       
        chat_ui.start_server_async()
        self._with_override("chat_ui", chat_ui)


async def new_invoke(self):  # noqa: C901
        # If there's no last user message, we need to wait for user input
        if self.message_hist[-1].role != Role.user:
            msg = await self.chat_ui.wait_for_user_input()
            if msg == "EXIT":
                return self.return_output()
            self.message_hist.append(
                UserMessage(
                    msg,
                )
            )

        ...
            
            else:
                # the message is malformed from the model
                raise LLMError(
                    reason="ModelLLM returned an unexpected message type.",
                    message_history=self.message_hist,
                )

        return self.return_output()

def new_return_output(self):
    """Returns the message history"""
    return self.message_hist


agent_chat = agent_node(
    name="cool_agent"
    ...
    chat_ui=chat_ui,
    return_ouput=new_return_output,
    invoke=new_invoke
)

```