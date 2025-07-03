import pytest
import requestcompletion as rc
from requestcompletion.context import put, get

class CapitalizeText(rc.Node[str]):
    def __init__(self, string: str, **kwargs):
        self.string = string
        super().__init__(**kwargs)

    async def invoke(self) -> str:
        return self.string.capitalize()

    @classmethod
    def pretty_name(cls) -> str:
        return "Capitalize Text"

    def format_for_context(self, result: str) -> None:
        """Store the result in context instead of returning it directly."""
        put("text_result", result)
        return None


@pytest.mark.asyncio
async def test_call_capitalize_text():
    node = CapitalizeText("hello world")
    assert await node.invoke() == "Hello world"
    assert node.pretty_name() == "Capitalize Text"


@pytest.mark.asyncio
async def test_call_capitalize_text_stream():
    node = CapitalizeText("")

    assert await node.invoke() == ""
    assert node.pretty_name() == "Capitalize Text"
