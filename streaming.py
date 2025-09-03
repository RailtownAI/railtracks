import asyncio

import litellm
import railtracks as rt
from pydantic import BaseModel


def secret_words(id: int):
    """
    Returns a secret phrase based on the id.
    Args:
        id (int): The id of the secret phrase to return.
    """
    rt.context.put("secret_words_called", True)
    secret_words = {
        0: "2 foxes and a dog",
        1: "3 cats and a dog",
        2: "4 foxes and a cat",
    }
    return secret_words[id]


class Schema(BaseModel):
    val: int


async def main():
    resp = litellm.completion(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": "invoke the secret_words tool with ids 1 and 0",
            },
        ],
        stream=True,
        tools=[
            {
                    "type": "function",
                    "function": {
                        "name": "secret_words",
                        "description": "Returns a secret phrase based on the id.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "id": {
                                    "type": "integer",
                                    "description": "The id of the secret phrase to return.",
                                },
                            },
                            "required": ["id"],
                        },
                    },
                }
        ]
    )
    print(resp)
    for chunk in resp.completion_stream:
        if chunk.choices:
            print(chunk.choices[0].delta.tool_calls)



asyncio.run(main())
