"""
Tests for the schema_parser module.

This module contains tests for the JSON output_schema parsing utilities in the
railtracks.llm.tools.schema_parser module.
"""

import re

from railtracks.llm.tools.schema_parser import (
    parse_json_schema_to_parameter,
    parse_model_properties,
)
from railtracks.llm.tools import Parameter, ArrayParameter, ObjectParameter, RefParameter


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

        assert isinstance(param, ArrayParameter)
        assert param.name == "test_param"
        assert param.description == "An array of objects"
        assert param.required is True
        assert isinstance(param.items, ObjectParameter)
        # Check nested properties
        for prop in param.items.properties:
            assert isinstance(prop, Parameter), "Expected Parameter object"
            if prop.name == "name":
                assert prop.param_type == "string"
                assert prop.required is True
            elif prop.name == "age":
                assert prop.param_type == "integer"
                assert prop.required is False
            else:
                assert False, f"Unexpected property name: {prop.name}"

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

        assert isinstance(param, ObjectParameter)
        assert param.name == "test_param"
        assert param.param_type == "object"
        assert param.description == "An object parameter"
        assert param.required is True

        # Check nested properties
        for prop in param.properties:
            assert isinstance(prop, Parameter), "Expected Parameter object"
            if prop.name == "name":
                assert prop.param_type == "string"
                assert prop.required is True
            elif prop.name == "age":
                assert prop.param_type == "integer"
                assert prop.required is False
            else:
                assert False, f"Unexpected property name: {prop.name}"

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

        assert isinstance(param, ObjectParameter)
        assert param.name == "test_param"
        assert param.param_type == "object"

        # Convert param.properties set to a list for easier processing
        properties_list = list(param.properties)

        # Check first level nested property
        person_prop = next(p for p in properties_list if p.name == "person")
        assert person_prop.required is True
        assert person_prop.param_type == "object"

        # Check second level nested property
        person_properties_list = list(person_prop.properties)
        name_prop = next(p for p in person_properties_list if p.name == "name")
        assert name_prop.required is True

        address_prop = next(p for p in person_properties_list if p.name == "address")
        assert address_prop.param_type == "object"

        # Check third level nested property
        address_properties_list = list(address_prop.properties)
        street_prop = next(p for p in address_properties_list if p.name == "street")
        city_prop = next(p for p in address_properties_list if p.name == "city")

        assert street_prop.required is True
        assert city_prop.required is False

    def test_parameter_with_ref(self):
        """Test parsing a parameter with a $ref."""
        schema = {
            "$ref": "#/components/schemas/Person",
            "description": "A reference to Person output_schema",
        }
        param = parse_json_schema_to_parameter("test_param", schema, True)

        assert isinstance(param, RefParameter)
        assert param.name == "test_param"
        assert param.param_type == "object"
        assert param.description == "A reference to Person output_schema"
        assert param.required is True

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
        """Test parsing an empty output_schema."""
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
        """Test parsing a simple output_schema with basic properties."""
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
        assert all(isinstance(param, Parameter) for param in result)

        # Convert result set to a list for easier processing
        params_list = list(result)
        result = {param.name: param for param in params_list}

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
        """Test parsing a output_schema with a nested object property."""
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
        assert all(isinstance(param, Parameter) for param in result)

        # Convert result set to a list for easier processing
        params_list = list(result)
        result = {param.name: param for param in params_list}

        assert "name" in result
        assert "address" in result

        # Check that address is a PydanticParameter with properties
        assert isinstance(result["address"], ObjectParameter)
        assert result["address"].param_type == "object"
        for param in result["address"].properties:
            assert isinstance(param, Parameter)
            if param.name == "street":
                assert param.required is True
            elif param.name == "city":
                assert param.required is False
            else:
                assert False, f"Unexpected property name: {param.name}"

    def test_schema_with_number_type(self):
        """Test parsing a output_schema with number type that should convert to float."""
        schema = {
            "properties": {"amount": {"type": "number", "description": "The amount"}}
        }

        result = parse_model_properties(schema)
        assert all(isinstance(param, Parameter) for param in result)
        params_list = list(result)
        result = {param.name: param for param in params_list}
        assert "amount" in result
        assert result["amount"].param_type == "number"

    def test_schema_with_defs_and_refs(self):
        """Test parsing a output_schema with $defs and $ref."""
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
        assert all(isinstance(param, Parameter) for param in result)
        params_list = list(result)
        result = {param.name: param for param in params_list}
        assert "name" in result
        assert "address" in result

        # Check that address is a PydanticParameter with properties from the $ref
        address_param = result["address"]
        assert isinstance(address_param, ObjectParameter)
        assert address_param.param_type == "object"
        address_properties = address_param.properties
        address_properties = {p.name: p for p in list(address_properties)}
        assert "street" in address_properties
        assert "city" in address_properties
        assert address_properties["street"].required is True
        assert address_properties["city"].required is False

    def test_schema_with_allof_and_refs(self):
        """Test parsing a output_schema with allOf and $ref."""
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
        assert all(isinstance(param, Parameter) for param in result)
        params_list = list(result)
        result = {param.name: param for param in params_list}
        assert "user" in result

        # Check that user is a PydanticParameter with properties from the $ref
        assert isinstance(result["user"], ObjectParameter)
        assert result["user"].param_type == "object"
        sub_params = list(result["user"].properties)
        sub_params = {p.name: p for p in sub_params}
        assert "name" in sub_params
        assert "age" in sub_params
        assert sub_params["name"].required is True
        assert sub_params["age"].required is False

    def test_empty_schema(self):
        """Test parsing an empty output_schema."""
        schema = {}

        result = parse_model_properties(schema)

        assert result == []

    def test_schema_without_properties(self):
        """Test parsing a output_schema without properties."""
        schema = {
            "title": "Test Schema",
            "description": "A test output_schema without properties",
        }

        result = parse_model_properties(schema)

        assert result == []
