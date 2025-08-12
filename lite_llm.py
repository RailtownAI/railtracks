import litellm

# =========== all models ==============
model_list = [
    "gpt-4o",
    "claude-3-5-sonnet-20240620",
    "gemini/gemini-2.5-pro",
    "huggingface/sambanova/meta-llama/Llama-3.3-70B-Instruct",
]
# =========== end all models ==============
model = model_list[3]

try:
    response = litellm.completion(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that criticizes the user's writing.",
            },
            {
                "role": "user",
                "content": "Here is my first paragraph: 'The sun was setting over the horizon, casting a warm glow over the landscape. The birds were chirping in the trees, and a gentle breeze rustled the leaves.'",
            },
        ],
    )
    print(response.choices[0].message.content)


except Exception as e:
    print(e)
