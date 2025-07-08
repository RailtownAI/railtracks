import requestcompletion as rc
import litellm

model = rc.llm.GeminiLLM(model_name="gemini-pro")


mh = rc.llm.MessageHistory(
    [
        rc.llm.SystemMessage("You are a helpful AI writing assistant."),
        rc.llm.UserMessage("Hello, how are you?"),
    ]
)

# resp = model.chat(mh)
response = litellm.completion(
    model="gemini/gemini-2.5-flash",
    messages=[{"role": "user", "content": "Hey"}],
    api_key="AIzaSyBRCR746N82nZPPHW-3NUD2QiiV4aNUONU",
    api_base=f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash",
)
print(response)
