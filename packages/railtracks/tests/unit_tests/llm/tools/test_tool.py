"""
Tests for the Tool class.

This module contains tests for railtracks.llm.tools.tool.Tool.
"""

import pytest
from railtracks.llm.tools import Tool
from railtracks.llm.tools.tool import ToolCreationError


class TestToolFromSchemaDict:
    def test_keeps_the_given_name(self):
        schema = {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "date": {"type": "string"},
            },
            "required": ["city"],
        }

        tool = Tool(
            name="Weather_1_GetWeather", detail="Get the weather.", parameters=schema
        )

        assert tool.name == "Weather_1_GetWeather"
        assert {p.name for p in tool.parameters} == {"city", "date"}
        assert {p.name for p in tool.parameters if p.required} == {"city"}

    def test_schema_without_properties(self):
        tool = Tool(
            name="no_args", detail="Takes nothing.", parameters={"type": "object"}
        )

        assert tool.name == "no_args"
        assert tool.parameters == []

    def test_required_without_properties_raises(self):
        with pytest.raises(ToolCreationError, match="no 'properties' block"):
            Tool(
                name="broken",
                detail="Declares a required field it never describes.",
                parameters={"type": "object", "required": ["city"]},
            )
