import litellm

response = litellm.completion(
    model="gemini/gemini-2.0-flash",
    messages=[{"role": "user", "content": "Hello what is your name?"}],
)
print(response.choices[0].message.content)
