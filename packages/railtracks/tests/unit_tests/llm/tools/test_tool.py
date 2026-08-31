"""
Tests for the Tool class.

This module contains tests for railtracks.llm.tools.tool.Tool.
"""

import pytest
from railtracks.exceptions.errors import NodeCreationError
from railtracks.llm.tools import Parameter, Tool
from railtracks.llm.tools.tool import ToolCreationError


class TestToolFromSchemaDict:
    def test_keeps_the_given_name(self):
        schema = {
            "type": "object",
            "additionalProperties": False,
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
            name="no_args",
            detail="Takes nothing.",
            parameters={
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            },
        )

        assert tool.name == "no_args"
        assert tool.parameters == []

    def test_required_without_properties_raises(self):
        with pytest.raises(ToolCreationError, match="no 'properties' block"):
            Tool(
                name="broken",
                detail="Declares a required field it never describes.",
                parameters={
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {},
                    "required": ["city"],
                },
            )

    def test_schema_missing_additional_properties_now_raises(self):
        """validate_tool_params is wired into __init__: a schema that never says
        additionalProperties: False used to construct a Tool silently and blow up
        later at LLM-call time instead."""
        with pytest.raises(NodeCreationError, match="additionalProperties"):
            Tool(
                name="incomplete",
                detail="Promises a property but never sets additionalProperties.",
                parameters={
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                },
            )


class TestToolParametersTypeGuard:
    def test_list_of_parameter_objects_is_accepted(self):
        tool = Tool(
            name="from_list",
            detail="Built with a list, like Tool.from_function produces.",
            parameters=[Parameter(name="city", param_type="string")],
        )

        assert [p.name for p in tool.parameters] == ["city"]

    def test_list_with_non_parameter_element_raises(self):
        with pytest.raises(NodeCreationError):
            Tool(
                name="bad_list",
                detail="A list that is not made of Parameter objects.",
                parameters=["city"],
            )
