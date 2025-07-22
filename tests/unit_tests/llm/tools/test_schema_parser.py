"""
Tests for the schema_parser module.

This module contains tests for the JSON schema parsing utilities in the
requestcompletion.llm.tools.schema_parser module.
"""

import re

from requestcompletion.llm.tools.schema_parser import (
    parse_json_schema_to_parameter,
    parse_model_properties,
)
from requestcompletion.llm.tools.parameter import Parameter, PydanticParameter


class TestParseJsonSchemaToParameter:
    """Tests for the parse_json_schema_to_parameter function."""

    def test_basic_string_parameter(self):
        """Test parsing a basic string parameter."""
        schema = {"type": "string", "description": "A string parameter"}
        param = parse_json_schema_to_parameter("test_param", schema, True)

        assert isinstance(param, Parameter)
        assert param.name == "test_param"
        assert param.param_type == "string"
        assert param.description == "A string parameter"
        assert param.required is True

    def test_basic_integer_parameter(self):
        """Test parsing a basic integer parameter."""
        schema = {"type": "integer", "description": "An integer parameter"}
        param = parse_json_schema_to_parameter("test_param", schema, False)

        assert isinstance(param, Parameter)
        assert param.name == "test_param"
        assert param.param_type == "integer"  # Should remain "integer"
        assert param.description == "An integer parameter"
        assert param.required is False

    def test_number_parameter_converts_to_float(self):
        """Test that 'number' type is converted to 'float'."""
        schema = {"type": "number", "description": "A number parameter"}
        param = parse_json_schema_to_parameter("test_param", schema, True)

        assert isinstance(param, Parameter)
        assert param.name == "test_param"
        assert param.param_type == "number"
        assert param.description == "A number parameter"
        assert param.required is True

    def test_boolean_parameter(self):
        """Test parsing a boolean parameter."""
        schema = {"type": "boolean", "description": "A boolean parameter"}
        param = parse_json_schema_to_parameter("test_param", schema, True)

        assert isinstance(param, Parameter)
        assert param.name == "test_param"
        assert param.param_type == "boolean"
        assert param.description == "A boolean parameter"
        assert param.required is True

    def test_array_parameter(self):
        """Test parsing an array parameter."""
        schema = {
            "type": "array",
            "description": "An array parameter",
            "items": {"type": "string"},
        }
        param = parse_json_schema_to_parameter("test_param", schema, True)

        assert isinstance(param, Parameter)
        assert param.name == "test_param"
        assert param.param_type == "array"
        assert param.description == "An array parameter"
        assert param.required is True

    def test_array_with_object_items(self):
        """Test parsing an array parameter with object items."""
        schema = {
            "type": "array",
            "description": "An array of objects",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The name"},
                    "age": {"type": "integer", "description": "The age"},
                },
                "required": ["name"],
            },
        }
        param = parse_json_schema_to_parameter("test_param", schema, True)

        assert isinstance(param, PydanticParameter)
        assert param.name == "test_param"
        assert param.param_type == "array"
        assert param.description == "An array of objects"
        assert param.required is True

        # Check nested properties
        assert "name" in param.properties
        assert "age" in param.properties
        assert param.properties["name"].required is True
        assert param.properties["age"].required is False
        assert param.properties["name"].param_type == "string"
        assert param.properties["age"].param_type == "integer"

    def test_object_parameter(self):
        """Test parsing an object parameter."""
        schema = {
            "type": "object",
            "description": "An object parameter",
            "properties": {
                "name": {"type": "string", "description": "The name"},
                "age": {"type": "integer", "description": "The age"},
            },
            "required": ["name"],
        }
        param = parse_json_schema_to_parameter("test_param", schema, True)

        assert isinstance(param, PydanticParameter)
        assert param.name == "test_param"
        assert param.param_type == "object"
        assert param.description == "An object parameter"
        assert param.required is True

        # Check nested properties
        assert "name" in param.properties
        assert "age" in param.properties
        assert param.properties["name"].required is True
        assert param.properties["age"].required is False
        assert param.properties["name"].param_type == "string"
        assert param.properties["age"].param_type == "integer"

    def test_nested_object_parameter(self):
        """Test parsing a deeply nested object parameter."""
        schema = {
            "type": "object",
            "description": "A nested object parameter",
            "properties": {
                "person": {
                    "type": "object",
                    "description": "Person details",
                    "properties": {
                        "name": {"type": "string", "description": "The name"},
                        "address": {
                            "type": "object",
                            "description": "Address details",
                            "properties": {
                                "street": {
                                    "type": "string",
                                    "description": "Street name",
                                },
                                "city": {"type": "string", "description": "City name"},
                            },
                            "required": ["street"],
                        },
                    },
                    "required": ["name"],
                }
            },
            "required": ["person"],
        }
        param = parse_json_schema_to_parameter("test_param", schema, True)

        assert isinstance(param, PydanticParameter)
        assert param.name == "test_param"
        assert param.param_type == "object"

        # Check first level nested property
        assert "person" in param.properties
        assert param.properties["person"].required is True
        assert param.properties["person"].param_type == "object"

        # Check second level nested property
        person = param.properties["person"]
        assert isinstance(person, PydanticParameter)
        assert "name" in person.properties
        assert "address" in person.properties
        assert person.properties["name"].required is True

        # Check third level nested property
        address = person.properties["address"]
        assert isinstance(address, PydanticParameter)
        assert "street" in address.properties
        assert "city" in address.properties
        assert address.properties["street"].required is True
        assert address.properties["city"].required is False

    def test_parameter_with_ref(self):
        """Test parsing a parameter with a $ref."""
        schema = {
            "$ref": "#/components/schemas/Person",
            "description": "A reference to Person schema",
        }
        param = parse_json_schema_to_parameter("test_param", schema, True)

        assert isinstance(param, PydanticParameter)
        assert param.name == "test_param"
        assert param.param_type == "object"
        assert param.description == "A reference to Person schema"
        assert param.required is True
        assert param.properties == {}  # Empty properties for now

    def test_default_type_is_object(self):
        """Test that the default type is 'object' when not specified."""
        schema = {"description": "A parameter without type"}
        param = parse_json_schema_to_parameter("test_param", schema, True)

        assert isinstance(param, Parameter)
        assert param.name == "test_param"
        assert param.param_type == "object"  # Default type
        assert param.description == "A parameter without type"
        assert param.required is True

    def test_empty_schema(self):
        """Test parsing an empty schema."""
        schema = {}
        param = parse_json_schema_to_parameter("test_param", schema, True)

        assert isinstance(param, Parameter)
        assert param.name == "test_param"
        assert param.param_type == "object"  # Default type
        assert param.description == ""
        assert param.required is True


class TestParseModelProperties:
    """Tests for the parse_model_properties function."""

    def test_simple_schema(self):
        """Test parsing a simple schema with basic properties."""
        schema = {
            "properties": {
                "name": {"type": "string", "description": "The name"},
                "age": {"type": "integer", "description": "The age"},
                "is_active": {
                    "type": "boolean",
                    "description": "Whether the user is active",
                },
            },
            "required": ["name", "age"],
        }

        result = parse_model_properties(schema)

        assert len(result) == 3
        assert "name" in result
        assert "age" in result
        assert "is_active" in result

        assert result["name"].param_type == "string"
        assert result["age"].param_type == "integer"
        assert result["is_active"].param_type == "boolean"

        assert result["name"].required is True
        assert result["age"].required is True
        assert result["is_active"].required is False

    def test_schema_with_nested_object(self):
        """Test parsing a schema with a nested object property."""
        schema = {
            "properties": {
                "name": {"type": "string", "description": "The name"},
                "address": {
                    "type": "object",
                    "description": "The address",
                    "properties": {
                        "street": {"type": "string", "description": "The street"},
                        "city": {"type": "string", "description": "The city"},
                    },
                    "required": ["street"],
                },
            },
            "required": ["name"],
        }

        result = parse_model_properties(schema)

        assert len(result) == 2
        assert "name" in result
        assert "address" in result

        # Check that address is a PydanticParameter with properties
        assert isinstance(result["address"], PydanticParameter)
        assert result["address"].param_type == "object"
        assert "street" in result["address"].properties
        assert "city" in result["address"].properties
        assert result["address"].properties["street"].required is True
        assert result["address"].properties["city"].required is False

    def test_schema_with_number_type(self):
        """Test parsing a schema with number type that should convert to float."""
        schema = {
            "properties": {"amount": {"type": "number", "description": "The amount"}}
        }

        result = parse_model_properties(schema)

        assert "amount" in result
        assert result["amount"].param_type == "number"

    def test_schema_with_defs_and_refs(self):
        """Test parsing a schema with $defs and $ref."""
        schema = {
            "$defs": {
                "Address": {
                    "properties": {
                        "street": {"type": "string", "description": "The street"},
                        "city": {"type": "string", "description": "The city"},
                    },
                    "required": ["street"],
                }
            },
            "properties": {
                "name": {"type": "string", "description": "The name"},
                "address": {"$ref": "#/$defs/Address", "description": "The address"},
            },
            "required": ["name"],
        }

        result = parse_model_properties(schema)

        assert len(result) == 2
        assert "name" in result
        assert "address" in result

        # Check that address is a PydanticParameter with properties from the $ref
        assert isinstance(result["address"], PydanticParameter)
        assert result["address"].param_type == "object"
        assert "street" in result["address"].properties
        assert "city" in result["address"].properties
        assert result["address"].properties["street"].required is True
        assert result["address"].properties["city"].required is False

    def test_schema_with_allof_and_refs(self):
        """Test parsing a schema with allOf and $ref."""
        schema = {
            "$defs": {
                "Person": {
                    "properties": {
                        "name": {"type": "string", "description": "The name"},
                        "age": {"type": "integer", "description": "The age"},
                    },
                    "required": ["name"],
                }
            },
            "properties": {
                "user": {
                    "allOf": [
                        {"$ref": "#/$defs/Person"},
                        {"type": "object", "description": "Additional user properties"},
                    ],
                    "description": "The user",
                }
            },
            "required": ["user"],
        }

        result = parse_model_properties(schema)

        assert len(result) == 1
        assert "user" in result

        # Check that user is a PydanticParameter with properties from the $ref
        assert isinstance(result["user"], PydanticParameter)
        assert result["user"].param_type == "object"
        assert "name" in result["user"].properties
        assert "age" in result["user"].properties
        assert result["user"].properties["name"].required is True
        assert result["user"].properties["age"].required is False

    def test_empty_schema(self):
        """Test parsing an empty schema."""
        schema = {}

        result = parse_model_properties(schema)

        assert result == {}

    def test_schema_without_properties(self):
        """Test parsing a schema without properties."""
        schema = {
            "title": "Test Schema",
            "description": "A test schema without properties",
        }

        result = parse_model_properties(schema)

        assert result == {}
