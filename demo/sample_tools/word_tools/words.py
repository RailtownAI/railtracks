from typing import List
from openai import OpenAI


def check_chars(input: str) -> int:
    client = OpenAI()
    
    print("Parsing image to text...")
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "You're a master charachter counter and no words fool you!"},
                    {
                        "type": "text",
                        "text": f"Count chars for the following word:{input}"
                    }
                ]
            }
        ]
        
    )
    
    extracted_text = response.choices[0].message.content
    print(f" :{extracted_text}")
    return 5
