# How to Run Your First Agent

Once you have defined your agent class you can then run your work flow and see results!

To begin you just have to use `call` for asynchronous flow or `call_sync` otherwise and pass your agent class as a parameter as well as the prompt as `user_input`:


###Example
```python

response = rt.call(
    weather_agent_class,
    user_input="Would you please be able to tell me the forecast for the next week?"
)
```

Just like that you have ran your first agent!

---

##Customization and Configurability

Although it really is that simple to run your agent, you can do more of course. If you have a dynamic work flow you can delay parameters to runtime and pass any number of args or kwargs and even the llm model you would like to use.


###Example
```python

dynamic_agent_class = rt.define_agent(
    agent_name="Weather Agent",
    system_message="You are a helpful assistant that answers weather-related questions. You have access to weather_tool which you should always consult when answering a question.",
    tools={weather_tool},
    schema=weather_schema,
    agent_params=weather_params
    agent_doc="This is an agent that will give you the current weather and answer weather related questions you have"    
)

response = rt.call(
    weather_agent_class,
    user_input="Would you please be able to tell me the forecast for the next week?",
    llm_model='claude-3-5-sonnet-20240620',
    weather_param_city='Vancouver',
    weather_param_provider='The Weather Network',
    weather_param_air_qual=True
)
```

##Retrieving The Results of a Run

All agents return a response object which you can use to get the required results.


<p style="text-align:center;">
  <a href="../tools_mcp/create_your_own" class="md-button" style="margin:3px">Create Your Own Agent</a>
  <a href="../advanced_usage/context" class="md-button" style="margin:3px">Using Context</a>
</p>
