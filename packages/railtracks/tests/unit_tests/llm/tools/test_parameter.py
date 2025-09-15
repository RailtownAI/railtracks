"""
Tests for the parameter module.

This module contains tests for the Parameter classes and related functionality
in the railtracks.llm.tools.parameter module.
"""

from railtracks.llm.tools.parameter import (
    Parameter,
    PydanticParameter,
)
from railtracks.llm.tools import Tool


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
            "description=A test parameter, required=False, "
            "additional_properties=False, "
            "enum=None, default=None)"
        )
        assert str(param) == expected_str

    def test_parameter_enum_and_default(self):
        """Test that Parameter correctly stores and returns enum and default values."""
        param = Parameter(
            name="enum_param",
            param_type="string",
            enum=["a", "b", "c"],
            default="b",
        )
        assert param.enum == ["a", "b", "c"]
        assert param.default == "b"
        assert "enum=['a', 'b', 'c']" in str(param)
        assert "default=b" in str(param)

    def test_parameter_with_none_default(self):
        """Test that Parameter correctly handles none as default value."""
        param = Parameter(name="test_param", param_type="string", default="none")
        assert param.default == "none"  

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

    def test_pydantic_parameter_refe_path(self):
        """Test that PydanticParameter correctly handles $ref path."""
        param = PydanticParameter(
            name="test_param",
            param_type="object",
            description="A test parameter",
            required=False,
            ref_path="test_path",
        )        
        assert param.ref_path == "test_path"
        assert "ref_path=test_path" in str(param)


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


class TestClassMethodParameters:
    """Tests for handling self and cls parameters in class methods."""

    def test_instance_method_self_parameter(self):
        """Test that self parameter is excluded from instance methods."""

        class TestClass:
            def instance_method(self, value: str) -> str:
                """
                Args:
                    value: The value to process
                Returns:
                    The processed value
                """
                return value.upper()

        tool = Tool.from_function(TestClass.instance_method)
        params = tool.parameters

        # Verify self is not in parameters
        assert all(param.name != "self" for param in params)
        # Verify value parameter is present
        assert any(param.name == "value" and param.param_type == "string" for param in params)

    def test_class_method_cls_parameter(self):
        """Test that cls parameter is excluded from class methods."""

        class TestClass:
            @classmethod
            def class_method(cls, value: str) -> str:
                """
                Args:
                    value: The value to process
                Returns:
                    The processed value
                """
                return value.upper()

        tool = Tool.from_function(TestClass.class_method)
        params = tool.parameters

        # Verify cls is not in parameters
        assert all(param.name != "cls" for param in params)
        # Verify value parameter is present
        assert any(param.name == "value" and param.param_type == "string" for param in params)
