import railtracks as rt

model = rt.llm.HuggingFaceLLM(
    "huggingface/featherless-ai/mistralai/Mistral-7B-Instruct-v0.2"
)
# model = rt.llm.HuggingFaceLLM("huggingface/together_ai/meta-llama/Llama-3.3-70B-Instruct")
model = rt.llm.GeminiLLM("gemini-2.5-flash")
model = rt.llm.OpenAILLM("gpt-4o")

@rt.function_node
def magic_number(number: int) -> int:
    return 3


simple_agent = rt.agent_node(
    tool_nodes={magic_number},
    name="Bot",
    llm_model=model,
)

response = rt.call_sync(simple_agent, "What is the magic number?")
print(response)

import litellm

magic_number_tool = {
    "type": "function",
    "function": {
        "name": "magic_number",
        "description": "",
        "parameters": {
            "type": "object",
            "properties": {"number": {"type": "integer"}},
            "required": ["number"],
        },
    },
}

# response = litellm.completion(
#     model="huggingface/sambanova/meta-llama/Llama-3.3-70B-Instruct", 
#     messages=[
#     {
#         "role": "user",
#         "content": "What's the magic number for 7?",
#     }
# ],
#     tools=[magic_number_tool],
#     tool_choice="auto"
# )

# print(response)