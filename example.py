import asyncio

import railtracks as rt

system_message = rt.llm.SystemMessage(
    "You are a helpful AI writing assistant. You should provide suggestions and corrections to the user's writing. Keep your advice concise and to the point."
)

# =========== all models ==============
model_list = []
model_list.append(rt.llm.OpenAILLM("gpt-4o"))
model_list.append(rt.llm.AnthropicLLM("claude-3-5-sonnet-20240620"))
model_list.append(rt.llm.GeminiLLM("gemini-2.5-pro"))
model_list.append(
    rt.llm.HuggingFaceLLM(model_name="sambanova/meta-llama/Llama-3.3-70B-Instruct")
)
# =========== end all models ==============

model = model_list[1]
WritingEditor = rt.agent_node(
    "Writing Editor", system_message=system_message, llm_model=model
)

mess_hist = rt.llm.MessageHistory(
    [
        rt.llm.UserMessage(
            "I am a writer who is working on a novel. Here is my first paragraph: 'The sun was setting over the horizon, casting a warm glow over the landscape. The birds were chirping in the trees, and a gentle breeze rustled the leaves.'"
        ),
    ]
)

# with rt.Session():
#     info = rt.call_sync(WritingEditor, user_input=mess_hist)

#     print(info.content)


async def test():
    with rt.Session():
        info = await rt.call(WritingEditor, user_input=mess_hist)

        print(info.content)


asyncio.run(test())
