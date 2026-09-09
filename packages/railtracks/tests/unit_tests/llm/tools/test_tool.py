"""
Tests for the Tool class.

This module contains tests for railtracks.llm.tools.tool.Tool.
"""

import pytest
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

    def test_schema_missing_additional_properties_is_accepted(self):
        """additionalProperties has no downstream effect (schema_parser.py and
        _handle_set_of_parameters both default a missing key to False, and the
        latter never re-emits the top-level key anyway), so a schema that omits
        it must still build a Tool normally."""
        tool = Tool(
            name="incomplete",
            detail="Promises a property but never sets additionalProperties.",
            parameters={
                "type": "object",
                "properties": {"city": {"type": "string"}},
            },
        )

        assert [p.name for p in tool.parameters] == ["city"]

    def test_schema_with_wrong_type_raises(self):
        with pytest.raises(ToolCreationError, match="'type' key set to 'object'"):
            Tool(
                name="wrong_type",
                detail="A schema whose outer type is not object.",
                parameters={"type": "array", "properties": {}},
            )


class TestToolParametersTypeGuard:
    def test_list_of_parameter_objects_is_accepted(self):
        tool = Tool(
            name="from_list",
            detail="Built with a list, like Tool.from_function produces.",
            parameters=[Parameter(name="city", param_type="string")],
        )

        assert [p.name for p in tool.parameters] == ["city"]

    def test_tuple_of_parameter_objects_is_accepted(self):
        tool = Tool(
            name="from_tuple",
            detail="A tuple of Parameter objects, not just set/list.",
            parameters=(Parameter(name="city", param_type="string"),),
        )

        assert [p.name for p in tool.parameters] == ["city"]

    def test_frozenset_of_parameter_objects_is_accepted(self):
        tool = Tool(
            name="from_frozenset",
            detail="A frozenset of Parameter objects, not just set/list.",
            parameters=frozenset({Parameter(name="city", param_type="string")}),
        )

        assert [p.name for p in tool.parameters] == ["city"]

    def test_generator_of_parameter_objects_is_not_exhausted(self):
        params = (Parameter(name=n, param_type="string") for n in ["city", "country"])
        tool = Tool(
            name="from_generator",
            detail="A single-pass iterable: validating it must not empty it.",
            parameters=params,
        )

        assert [p.name for p in tool.parameters] == ["city", "country"]

    def test_list_with_non_parameter_element_raises(self):
        with pytest.raises(ToolCreationError, match="iterable of Parameter objects"):
            Tool(
                name="bad_list",
                detail="A list that is not made of Parameter objects.",
                parameters=["city"],
            )

    def test_non_iterable_non_dict_raises(self):
        with pytest.raises(ToolCreationError, match="iterable of Parameter objects"):
            Tool(
                name="bad_type",
                detail="An int is neither a dict nor an iterable of Parameter objects.",
                parameters=1,
            )
