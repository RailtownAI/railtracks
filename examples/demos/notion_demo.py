import requestcompletion as rc
from requestcompletion.llm import MessageHistory, UserMessage
from ..sample_agents.notion_agent import notion_agent
import asyncio



"""Make sure you have Node.js installed"""
"""To see better results initialize NOTION_ROOT_PAGE_ID variable in your .env file with the ID of the page you want to use as the parent page for your operations.
Otherwise you can specify the title of the parent page in the system message"""

USER_PROMPT = """Would you be able to create a new page for me in Notion labeled "Jokes"? I would like to have a small joke at the top of the page. Anything but the scientist joke please."""


notion_agent = notion_agent(model=rc.llm.OpenAILLM("gpt-4o"))

with rc.Runner() as run:
    result = asyncio.run(
        run.run(
            notion_agent,
            instructions=USER_PROMPT,
        )
    )
