"""
Tests for the parameter module.

This module contains tests for the Parameter classes and related functionality
in the requestcompletion.llm.tools.parameter module.
"""

import pytest
from copy import deepcopy

from src.requestcompletion.llm.tools.parameter import (
    ParameterType,
    Parameter,
    PydanticParameter,
)

class TestParameter:
    """Tests for the Parameter base class."""

    def test_parameter_initialization(self):
        """Test that Parameter objects can be initialized with expected values."""
        param = Parameter(
            name="test_param",
            param_type="string",
            description="A test parameter",
            required=True,
        )
        
        assert param.name == "test_param"
        assert param.param_type == "string"
        assert param.description == "A test parameter"
        assert param.required is True

    def test_parameter_default_values(self):
        """Test that Parameter objects use default values correctly."""
        param = Parameter(name="test_param", param_type="integer")
        
        assert param.name == "test_param"
        assert param.param_type == "integer"
        assert param.description == ""
        assert param.required is True

    def test_parameter_string_representation(self):
        """Test the string representation of Parameter objects."""
        param = Parameter(
            name="test_param",
            param_type="boolean",
            description="A test parameter",
            required=False,
        )
        
        expected_str = (
            "Parameter(name=test_param, type=boolean, "
            "description=A test parameter, required=False)"
        )
        assert str(param) == expected_str

    def test_type_mapping(self):
        """Test that type_mapping returns the expected mapping."""
        mapping = Parameter.type_mapping()
        
        assert mapping["string"] is str
        assert mapping["integer"] is int
        assert mapping["float"] is float
        assert mapping["boolean"] is bool
        assert mapping["array"] is list
        assert mapping["object"] is dict

class TestPydanticParameter:
    """Tests for the PydanticParameter class."""

    def test_pydantic_parameter_initialization(self):
        """Test that PydanticParameter objects can be initialized with expected values."""
        param = PydanticParameter(
            name="test_param",
            param_type="object",
            description="A test parameter",
            required=True,
            properties={},
        )
        
        assert param.name == "test_param"
        assert param.param_type == "object"
        assert param.description == "A test parameter"
        assert param.required is True
        assert param.properties == {}

    def test_pydantic_parameter_default_properties(self):
        """Test that PydanticParameter uses an empty dict for properties by default."""
        param = PydanticParameter(name="test_param", param_type="object")
        
        assert param.properties == {}

    def test_pydantic_parameter_with_nested_properties(self):
        """Test PydanticParameter with nested properties."""
        nested_param = Parameter(
            name="nested", param_type="string", description="A nested parameter"
        )
        
        param = PydanticParameter(
            name="test_param",
            param_type="object",
            properties={"nested": nested_param},
        )
        
        assert param.properties["nested"] is nested_param
        assert param.properties["nested"].name == "nested"
        assert param.properties["nested"].param_type == "string"

    def test_pydantic_parameter_string_representation(self):
        """Test the string representation of PydanticParameter objects."""
        nested_param = Parameter(name="nested", param_type="string")
        param = PydanticParameter(
            name="test_param",
            param_type="object",
            description="A test parameter",
            required=False,
            properties={"nested": nested_param},
        )
        
        # The string representation should include properties
        str_repr = str(param)
        assert "PydanticParameter" in str_repr
        assert "name=test_param" in str_repr
        assert "type=object" in str_repr
        assert "required=False" in str_repr
        assert "properties=" in str_repr
        assert "nested" in str_repr

class TestParameterEdgeCases:
    """Tests for edge cases and validation in Parameter classes."""

    def test_deep_nested_pydantic_parameters(self):
        """Test deeply nested PydanticParameter structures."""
        level3 = Parameter(name="level3", param_type="string")
        level2 = PydanticParameter(
            name="level2", param_type="object", properties={"level3": level3}
        )
        level1 = PydanticParameter(
            name="level1", param_type="object", properties={"level2": level2}
        )
        
        assert level1.properties["level2"].properties["level3"] is level3
        assert level1.properties["level2"].properties["level3"].param_type == "string"

    def test_properties_are_isolated(self):
        """Test that modifying properties in one instance doesn't affect others."""
        param1 = PydanticParameter(name="param1", param_type="object")
        param2 = PydanticParameter(name="param2", param_type="object")
        
        # Add a property to param1
        param1.properties["new_prop"] = Parameter(name="new", param_type="string")
        
        # param2's properties should still be empty
        assert "new_prop" not in param2.properties
