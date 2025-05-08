from openai import OpenAI
import sys
import os
import json
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

# Add the parent directory of "demo" to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from demo.sample_tools.notion_tools import find_page, get_block_text, get_text_blocks, edit_block

def call_function(name, args):
    if name == "find_page":
        return find_page(**args)
    if name == "get_block_text":
        return get_block_text(**args)
    if name == "get_text_blocks":
        return get_text_blocks(**args)
    if name == "edit_block":
        return edit_block(**args)
    

client = OpenAI()

tools = [{
    "type": "function",
    "name": "find_page",
    "description": "Search for pages in Notion workspace by query string.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query string to find pages"
            },
        },
        "required": [
            "query"
        ],
        "additionalProperties": False
    },
    "strict": True
    },
    {
    "type": "function",
    "name": "get_block_text",
    "description": "Get the text from a simple text block",
    "parameters": {
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "id of the parent page"
            },
            "block_id": {
                "type": "string",
                "description": "id of the block to get text from"
            }
        },
        "required": [
            "page_id", "block_id"
        ],
        "additionalProperties": False
    },
    "strict": True
    },
    {
    "type": "function",
    "name": "get_text_blocks",
    "description": "Get a list of block id's to be edited",
    "parameters": {
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "id of the parent page"
            }
        },
        "required": [
            "page_id"
        ],
        "additionalProperties": False
    },
    "strict": True
    },
    {
    "type": "function",
    "name": "edit_block",
    "description": "Edit existing block",
    "parameters": {
        "type": "object",
        "properties": {
            "page_id": {
                "type": "string",
                "description": "id of the parent page"
            },
            "block_id": {
                "type": "string",
                "description": "id of the block to get text from"
            },
            "new_text": {
                "type": "string",
                "description": "The text to update the block with"
            }
        },
        "required": [
            "page_id", "block_id", "new_text"
        ],
        "additionalProperties": False
    },
    "strict": True
    }]

SYSTEM_PROMPT = """
    You are a professional editor with greatest knowledge of 
    how the english language works and love to edit passages 
    for people to fix their spelling and grammar. You have 
    acess to find_page, get_block_text, get_text_blocks, 
    and edit_block. Use them when you see fit.
    """


USER_PROMPT = "Would you be able to edit my page for me? It's under `Agent Demo Root`, in the page `Page To Be Editd` "

messages = [{ "role": "system", "content": SYSTEM_PROMPT },
  { "role": "user", "content": USER_PROMPT }]

tool_calls = True
i = 0
while tool_calls and i < 10:
    response = client.responses.create(
        model="gpt-4o",
        instructions=SYSTEM_PROMPT,
        input=USER_PROMPT,
        tools=tools
    )

    tool_calls = False
    for tool_call in response.output:
        if tool_call.type != "function_call":
            messages.append(tool_call)
            continue

        tool_calls = True
        name = tool_call.name
        args = json.loads(tool_call.arguments)

        result = call_function(name, args)

  

        messages.append({
            "type": "function_call_output",
            "call_id": tool_call.call_id,
            "output": str(result)
        })
        print(messages[-1]) 

 
        
        print("\n") 
    i += 1

