# --8<-- [start: prompt_basic]
import railtracks as rt

# Define a prompt with placeholders
system_message = "You are a {role} assistant specialized in {domain}."

# Create an LLM node with this prompt
assistant = rt.agent_node(
    name="Assistant",
    system_message=system_message,
    llm=rt.llm.OpenAILLM("gpt-4o"),
)

# Run with context values
with rt.Session(context={"role": "technical", "domain": "Python programming"}):
    response = await rt.call(assistant, user_input="Help me understand decorators.")

# --8<-- [end: prompt_basic]

# --8<-- [start: disable_injection]
# Disable context injection for a specific run
with rt.Session(
    prompt_injection=False
): ...

# or globally via 
rt.set_config(prompt_injection=False)
# --8<-- [end: disable_injection]

# --8<-- [start: injection_at_message_level]
# This message will have context injection applied
system_msg = rt.llm.Message(role="system", content="You are a {role}.", inject_prompt=True)

# This message will not have context injection applied
user_msg = rt.llm.Message(role="user", content="Tell me about {topic}.", inject_prompt=False)
# --8<-- [end: injection_at_message_level]

# --8<-- [start: prompt_templates]
import railtracks as rt
from railtracks.llm import OpenAILLM

# Define a template with multiple placeholders
template = """You are a {assistant_type} assistant.
Your task is to help the user with {task_type} tasks.
Use a {tone} tone in your responses.
The user's name is {user_name}."""

# Create an LLM node with this template
assistant = rt.agent_node(
    name="Dynamic Assistant",
    system_message=template,
    llm=OpenAILLM("gpt-4o"),
)

# Different context for different scenarios
customer_support_context = {
    "assistant_type": "customer support",
    "task_type": "troubleshooting",
    "tone": "friendly and helpful",
    "user_name": "Alex"
}

technical_expert_context = {
    "assistant_type": "technical expert",
    "task_type": "programming",
    "tone": "professional",
    "user_name": "Taylor"
}

# Run with different contexts for different scenarios
with rt.Session(context=customer_support_context):
    response1 = await rt.call(assistant, user_input="My product isn't working.")

with rt.Session(context=technical_expert_context):
    response2 = await rt.call(assistant, user_input="How do I implement a binary tree?")
# --8<-- [end: prompt_templates]
