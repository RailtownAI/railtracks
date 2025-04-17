import os
from notion_client import Client
from dotenv import load_dotenv
from pydantic import BaseModel
from enum import Enum
from typing import Optional

load_dotenv()
notion = Client(auth=os.environ["NOTION_TOKEN"])

ROOT_PAGE_ID = ""

class PageProperties(BaseModel):
    id: str
    title: str

class NewPageProperties(BaseModel):
    parent_id: str
    title: str

class BlockType(Enum):
    PARAGRAPH = "paragraph"
    CODE = "code"
    HEADING_1 = "heading_1"
    HEADING_2 = "heading_2"
    HEADING_3 = "heading_3"
    BULLETED_LIST = "bulleted_list_item"
    NUMBERED_LIST = "numbered_list_item"
    TO_DO = "to_do"
    QUOTE = "quote"

class BlockProperties(BaseModel):
    page_id: str
    content: str
    block_type: BlockType = BlockType.PARAGRAPH
    language: Optional[str] = None  # For code blocks: python, javascript, etc.

class UserProperties(BaseModel):
    id: str
    name: str
    type: str
    avatar_url: Optional[str]

def find_user(query: str) -> list[UserProperties]:
    """
    Search for users in Notion workspace by query string.

    Args:
        query (str): Search query string to find users

    Returns:
        list[UserProperties]: List of found users with their properties
    """
    results = notion.users.list()
    users = []

    for user in results["results"]:
        # Check if name matches query (case-insensitive)
        name = user.get("name", "")
        if query.lower() in name.lower():
            users.append(UserProperties(
                id=user["id"],
                name=name,
                type=user["type"],
                avatar_url=user.get("avatar_url")
            ))

    return users

def tag_user(page_id: str, user_id: str, text: str = "") -> None:
    """
    Add a mention/tag of a user to a Notion page.

    Args:
        page_id (str): ID of the page to add the mention to
        user_id (str): ID of the user to mention
        text (str): Optional text to add alongside the mention

    Returns:
        None
    """
    mention_block = {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {
                    "type": "mention",
                    "mention": {
                        "type": "user",
                        "user": {
                            "id": user_id
                        }
                    }
                }
            ]
        }
    }

    # Add additional text if provided
    if text:
        mention_block["paragraph"]["rich_text"].append({
            "type": "text",
            "text": {
                "content": f" {text}"
            }
        })

    notion.blocks.children.append(
        block_id=page_id,
        children=[mention_block]
    )

def find_page(query: str) -> list[PageProperties]:
    """
    Search for pages in Notion workspace by query string.

    Args:
        query (str): Search query string to find pages

    Returns:
        list[PageProperties]: List of found pages with their IDs and titles
    """
    results = notion.search(query=query)
    page_ids = []

    for result in results["results"]:
        if result["object"] == "page":
            page_ids.append(PageProperties(
                id=result["id"], 
                title=result["properties"]["title"]["title"][0]["text"]["content"]
            ))

    return page_ids


def create_page(properties: NewPageProperties) -> str:
    """
    Create a new page in Notion workspace and returns its id.

    Args:
        properties (NewPageProperties): Properties for the new page including parent_id and title

    Returns:
        str: ID of the created page
    """
    response = notion.pages.create(
        parent={"type": "page_id", "page_id": properties.parent_id},
        properties={"title": [{"text": {"content": properties.title}}]},
    )
    return response["id"]


def add_block(properties: BlockProperties) -> None:
    """
    Add a new block to an existing Notion page.

    Args:
        properties (BlockProperties): Properties for the new block including:
            - page_id: ID of the parent page
            - content: Text content of the block
            - block_type: Type of block (paragraph, code, heading, etc.)
            - language: Programming language for code blocks

    Returns:
        None
    """
    block_content = {
        "object": "block",
        "type": properties.block_type.value,
    }

    if properties.block_type == BlockType.CODE:
        code_block = {
            "rich_text": [{"text": {"content": properties.content}}],
            "language": properties.language or "plain text"
        }
        
        block_content[properties.block_type.value] = code_block
    else:
        block_content[properties.block_type.value] = {
            "rich_text": [{"text": {"content": properties.content}}]
        }

    notion.blocks.children.append(
        block_id=properties.page_id,
        children=[block_content]
    )