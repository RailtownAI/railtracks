import railtracks as rt
from pydantic import BaseModel, Field
import litellm


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

async def main():
    resp = await litellm.acompletion(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": "give me a 100 word using the secret_words tool"},
        ],
        stream=True,
        # tools=[
        #     {
        #             "type": "function",
        #             "function": {
        #                 "name": "secret_words",
        #                 "description": "Returns a secret phrase based on the id.",
        #                 "parameters": {
        #                     "type": "object",
        #                     "properties": {
        #                         "id": {
        #                             "type": "integer",
        #                             "description": "The id of the secret phrase to return.",
        #                         },
        #                     },
        #                     "required": ["id"],
        #                 },
        #             },
        #         }
        # ]
    )

    async for chunk in resp.completion_stream:
        print(chunk)

import asyncio

asyncio.run(main())