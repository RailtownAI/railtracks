Quite often an agentic workflow needs further input from a human user (or another agent) in a muli-turn style conversation or verification.

Revisiting the figure from the background on [agents](../background/agents.md), we can take a new view:

```mermaid
graph LR
    User[User] <-- "Input/Output" --> LLM[LLM Agent]
    LLM <--> Tools[Tools]
    LLM <-- "Iterative Input/Output" --> Environment[User, Other Users, Other Agents]
    User <-- "Iterative Input/Output" --> Environment

    style LLM fill:#e1f5fe
    style User fill:#f3e5f5
    style Tools fill:#fff3e0
    style Environment fill:#e8f5e8
```

To allow this for the users of the framework, we have designed an extendible abstract class called `HIL` (*Human In the Loop*). Additionally we have implemented a local chat server for quick development and prototyping of such behaviours. Please refer to the following sections for futher information:

* [Local ChatUI](local_chat_ui.md)
* [Custom HIL Behaviour](hil.md)