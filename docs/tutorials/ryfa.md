# How to Run Your First Agent

Once you have defined your agent class you can then run your work flow and see results!

To begin you just have to use `call` for asynchronous flows or `call_sync` if it's s sequential flow. You simply pass your agent node as a parameter as well as the prompt as `user_input`:


### Example
```python

response = rt.call(
    weather_agent_class,
    user_input="Would you please be able to tell me the forecast for the next week?"
)
```

Just like that you have ran your first agent!

---

## Customization and Configurability

Although it really is that simple to run your agent, you can do more of course. If you have a dynamic work flow you can delay parameters like `llm_model` and you can add a `SystemMessage` along with your prompt directly to `user_input` as a `MessageHistory` object.

### Example
```python

weather_agent_class = rt.agent_node(
    tool_nodes={weather_tool},
    output_schema=weather_schema, 
)

system_message = rt.message.SystemMessage("You are a helpful assistant that answers weather-related questions.")
user_message = rt.message.UserMessage("Would you please be able to tell me the forecast for the next week?")

response = rt.call(
    weather_agent_class,
    user_input=MessageHistory([system_message, user_message]),
    llm_model='claude-3-5-sonnet-20240620',
)
```

Should you pass `llm_model` to `agent_node` and then a different llm model to either call function, RailTracks will use the parameter passed in the call. If you pass `system_message` to `agent_node` and then another `system_message` to a call function, the system messages will be stacked.

### Example
```python

default_model = "gpt-40"
default_system_message = "You are a helpful assistant that answers weather-related questions."

weather_agent_class = rt.agent_node(
    tool_nodes={weather_tool},
    system_message=default_system_message,
    llm_model=default_model,
)

system_message = rt.message.SystemMessage("If not specified, the user is talking about Vancouver.")
user_message = rt.message.UserMessage("Would you please be able to tell me the forecast for the next week?")

response = rt.call(
    weather_agent_class,
    user_input=MessageHistory([system_message, user_message]),
    llm_model='claude-3-5-sonnet-20240620',
)
```
In this example RailTracks will use claude rather than chatgpt and the system message will become
"You are a helpful assistant that answers weather-related questions. If not specified, the user is talking about Vancouver."

## Retrieving The Results of a Run

All agents return a response object which you can use to get the last message or the entire message history if you would prefer.

### Unstructured Response Example
```python

coding_agent_node = rt.agent_node()

system_message = rt.message.SystemMessage("You are an assistant that helps users write code and learn about coding.")
user_message = rt.message.UserMessage("Would you be able to help me figure out a good solution to running agentic flows?")

response = rt.call(
    coding_agent_node,
    user_input=MessageHistory([system_message, user_message]),
    llm_model='claude-3-5-sonnet-20240620',
)

answer_string = response.text()
message_history_object = response.message_history
```

### Structured Response Example
```python
from pydantic import BaseModel

class User(BaseModel):
    user_number : int
    age: int
    name: str

agent_node = rt.agent_node(
    output_schema=User,
    system_message=agent_message,
    llm_model="gpt-4o"
)

response = rt.call(
    agent_class,
    user_input=input_str
)

user_number = response.structured().user_number
message_history_object = response.message_history
```

## Advanced Usage Examples

### Deciding Precise Run Time Calls

```python

class stocks(BaseModel):
    action : str 

def find_stocks(...):
    ...

def own_stocks(...):
    ...

def analyze_stock(...):
    ...

def buy_stocks(...):
    ...

def sell_stocks(...):
    ...

scoutNode = agent_node(
    name="Scout Node",
    system_message="""You are a trading agent that helps find the best stocks to buy and sell. To find stocks you can use the find_stocks tool,
    to see which stocks you own you can use own_stocks tool, and to analyze""" 
)
buyingNode = function_node(buy_stocks)
sellingNode = function_node(sell_stocks)

while stillHaveMoney:
    stocks = rt.call(scoutNode)

    if stocks.structure[action] = "buy" 

```

### The power of RailTracks

```python

class ShortAndLongSummaries(BaseModel):
    OneLineSummarry: str = Field(description="One line summary of the commit")
    DetailedSummary: str = Field(description="Detailed summary of the commit")

system_prompt = """You are an expert software developer and manager. Your job is to look at developers' code updates, and summarize what was done in a brief but understable way. 
                        Always provide only the summary - no acknowledgements or greetings. You are to generate a brief one-line summary as well as a longer more detailed one. 
                        Be sure to focus on the function or purpose of the changes made rather than the minutiae of the code changes. If the diff is short, your detailed summary can be brief."""


CommitSummarizerNode = agent_node(
    output_schema=ShortAndLongSummaries,
    system_message=system_prompt)


async def top_level_summarizer(Summarize, commit_diffs, prompt_data) -> list[dict]: 
    """
    Top level node for the commit summarizer
    """
    contracts = [rc.call(Summarize, commit_diff, prompt_data) for commit_diff in commit_diffs]

    results = await asyncio.gather(*contracts)
    return results

async def summarize(commit: types.CommitData, prompt_data: dict) -> dict:
    """
    Summarize a commit using the provided prompt data
    """
    full_diff = combine_file_diffs(commit.FileDiffs)
    user_prompt = prompt_data["UserPrompt"].format(
        diff=full_diff, commit_message=commit.CommitMessage
    )

    message_history = rc.llm.MessageHistory(
        [
            rc.llm.UserMessage(user_prompt),
        ]
    )

    response = await rc.call(CommitSummarizerNode, message_history, prompt_data["llm_prompt"])
    
    return {commit.CommitSha: response}

results = rt.call(CommitSummarizer, Summarize, payload.Commits, prompt_data)
```



<p style="text-align:center;">
  <a href="../tools_mcp/create_your_own" class="md-button" style="margin:3px">Create Your Own Agent</a>
  <a href="../advanced_usage/context" class="md-button" style="margin:3px">Using Context</a>
</p>
