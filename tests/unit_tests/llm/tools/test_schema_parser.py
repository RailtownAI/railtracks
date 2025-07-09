"""
Tests for the schema_parser module.

This module contains tests for the JSON schema parsing utilities in the
requestcompletion.llm.tools.schema_parser module.
"""

import re

from requestcompletion.llm.tools.schema_parser import (
    parse_json_schema_to_parameter,
    parse_model_properties,
    convert_params_to_model_recursive,
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
        assert param.param_type == "float"  # Should be converted to "float"
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
        assert result["amount"].param_type == "float"  # Should be converted to float

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


class TestConvertParamsToModelRecursive:
    """Tests for the convert_params_to_model_recursive function."""

    def test_basic_parameter_conversion(self):
        """Test converting basic parameters to a Pydantic model."""
        parameters = {
            "name": Parameter(
                name="name", param_type="string", description="The name", required=True
            ),
            "age": Parameter(
                name="age", param_type="integer", description="The age", required=True
            ),
            "is_active": Parameter(
                name="is_active",
                param_type="boolean",
                description="Active status",
                required=False,
            ),
        }

        model = convert_params_to_model_recursive("TestModel", set(parameters.values()))

        # Check model properties
        assert hasattr(model, "model_fields")

        # Check field types
        assert model.model_fields["name"].annotation == str
        assert model.model_fields["age"].annotation == int
        assert "Optional" in str(model.model_fields["is_active"].annotation)
        assert "bool" in str(model.model_fields["is_active"].annotation)

        # Check field descriptions
        assert model.model_fields["name"].description == "The name"
        assert model.model_fields["age"].description == "The age"
        assert model.model_fields["is_active"].description == "Active status"

        # Check required status
        assert model.model_fields["name"].is_required() is True
        assert model.model_fields["age"].is_required() is True
        assert model.model_fields["is_active"].is_required() is False

    def test_nested_object_conversion(self):
        """Test converting nested object parameters to a Pydantic model."""
        address_props = {
            "street": Parameter(
                name="street",
                param_type="string",
                description="The street",
                required=True,
            ),
            "city": Parameter(
                name="city", param_type="string", description="The city", required=False
            ),
        }

        parameters = {
            "name": Parameter(
                name="name", param_type="string", description="The name", required=True
            ),
            "address": PydanticParameter(
                name="address",
                param_type="object",
                description="The address",
                required=True,
                properties=address_props,
            ),
        }

        model = convert_params_to_model_recursive("TestModel", set(parameters.values()))

        # Check model properties
        assert hasattr(model, "model_fields")

        # Check field types
        assert model.model_fields["name"].annotation == str

        # The address field should be a nested model
        address_field_type = model.model_fields["address"].annotation
        assert "TestModel_address" in str(address_field_type)

        # Create an instance to check nested model structure
        address_model = address_field_type
        assert hasattr(address_model, "model_fields")
        assert "street" in address_model.model_fields
        assert "city" in address_model.model_fields
        assert address_model.model_fields["street"].annotation == str
        assert "Optional" in str(address_model.model_fields["city"].annotation)

    def test_array_conversion(self):
        """Test converting array parameters to a Pydantic model."""
        parameters = {
            "name": Parameter(
                name="name", param_type="string", description="The name", required=True
            ),
            "tags": Parameter(
                name="tags", param_type="array", description="The tags", required=False
            ),
        }

        model = convert_params_to_model_recursive("TestModel", set(parameters.values()))

        # Check model properties
        assert hasattr(model, "model_fields")

        # Check field types
        assert model.model_fields["name"].annotation == str
        assert "Optional" in str(model.model_fields["tags"].annotation)
        assert "list" in str(model.model_fields["tags"].annotation).lower()

    def test_array_with_nested_objects(self):
        """Test converting array parameters with nested objects to a Pydantic model."""
        item_props = {
            "id": Parameter(
                name="id", param_type="integer", description="The ID", required=True
            ),
            "value": Parameter(
                name="value",
                param_type="string",
                description="The value",
                required=True,
            ),
        }

        parameters = {
            "name": Parameter(
                name="name", param_type="string", description="The name", required=True
            ),
            "items": PydanticParameter(
                name="items",
                param_type="array",
                description="The items",
                required=True,
                properties=item_props,
            ),
        }

        model = convert_params_to_model_recursive("TestModel", set(parameters.values()))

        # Check model properties
        assert hasattr(model, "model_fields")

        # Check field types
        assert model.model_fields["name"].annotation == str

        # The items field should be a list of a nested model
        items_field_type = model.model_fields["items"].annotation
        assert "List" in str(items_field_type)

        # Extract the nested model type from List[...]
        nested_model_match = re.search(r"List\[(.*?)\]", str(items_field_type))
        assert nested_model_match

        # The nested model should have the expected fields
        nested_model_name = nested_model_match.group(1).strip()
        assert "TestModel_items" in nested_model_name

    def test_all_parameter_types(self):
        """Test converting all parameter types to a Pydantic model."""
        parameters = {
            "string_param": Parameter(
                name="string_param",
                param_type="string",
                description="String param",
                required=True,
            ),
            "integer_param": Parameter(
                name="integer_param",
                param_type="integer",
                description="Integer param",
                required=True,
            ),
            "float_param": Parameter(
                name="float_param",
                param_type="float",
                description="Float param",
                required=True,
            ),
            "boolean_param": Parameter(
                name="boolean_param",
                param_type="boolean",
                description="Boolean param",
                required=True,
            ),
            "array_param": Parameter(
                name="array_param",
                param_type="array",
                description="Array param",
                required=True,
            ),
            "object_param": Parameter(
                name="object_param",
                param_type="object",
                description="Object param",
                required=True,
            ),
        }

        model = convert_params_to_model_recursive("TestModel", set(parameters.values()))

        # Check model properties
        assert hasattr(model, "model_fields")

        # Check field types
        assert model.model_fields["string_param"].annotation == str
        assert model.model_fields["integer_param"].annotation == int
        assert model.model_fields["float_param"].annotation == float
        assert model.model_fields["boolean_param"].annotation == bool
        assert "list" in str(model.model_fields["array_param"].annotation).lower()
        assert model.model_fields["object_param"].annotation == dict

    def test_optional_parameters(self):
        """Test converting optional parameters to a Pydantic model."""
        parameters = {
            "required_param": Parameter(
                name="required_param",
                param_type="string",
                description="Required param",
                required=True,
            ),
            "optional_param": Parameter(
                name="optional_param",
                param_type="string",
                description="Optional param",
                required=False,
            ),
        }

        model = convert_params_to_model_recursive("TestModel", set(parameters.values()))

        # Check model properties
        assert hasattr(model, "model_fields")

        # Check field types and required status
        assert model.model_fields["required_param"].annotation == str
        assert "Optional" in str(model.model_fields["optional_param"].annotation)
        assert model.model_fields["required_param"].is_required() is True
        assert model.model_fields["optional_param"].is_required() is False

    def test_empty_parameters(self):
        """Test converting an empty set of parameters."""
        model = convert_params_to_model_recursive("TestModel", set())

        # The model should exist but have no fields
        assert hasattr(model, "model_fields")
        assert len(model.model_fields) == 0

    def test_model_config(self):
        """Test that the generated model has the correct configuration."""
        parameters = {
            "name": Parameter(
                name="name", param_type="string", description="The name", required=True
            )
        }

        model = convert_params_to_model_recursive("TestModel", set(parameters.values()))

        # Check that the model has extra="forbid" to ensure additionalProperties=False
        assert hasattr(model, "model_config")
        assert model.model_config.get("extra") == "forbid"
