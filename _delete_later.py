import railtracks as rt
import litellm

model = rt.llm.GeminiLLM(model_name="gemini-pro")


mh = rt.llm.MessageHistory(
    [
        rt.llm.SystemMessage("You are a helpful AI writing assistant."),
        rt.llm.UserMessage("Hello, how are you?"),
    ]
)

# resp = model.chat(mh)
response = litellm.completion(
    model="gemini/gemini-2.5-flash",
    messages=[{"role": "user", "content": "Hey"}],
)
print(response)
