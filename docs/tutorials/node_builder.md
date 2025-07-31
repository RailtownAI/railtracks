# How to Customize Class Building

RailTracks `define_agent` allows user to configure agent classes with set parameters you can choose from. These parameters suffice for most cases but what if you want to make an agent with just slightly more functionality? RailTracks has you covered again! Using our NodeBuilder class you can create your own agent class with many of the same functionalities provided in `define_agent` but the option to add class methods and attributes of your choice. 

---


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