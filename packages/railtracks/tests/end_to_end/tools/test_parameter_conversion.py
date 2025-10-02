import pytest
import copy
from railtracks.llm.models._litellm_wrapper import _parameters_to_json_schema
from railtracks.llm.tools.schema_parser import parse_json_schema_to_parameter
import json
from .conftest import load_json_schemas, deep_equal

schemas = load_json_schemas()

@pytest.mark.parametrize("input_schema", [pytest.param(s, id=f"Case {i}") for i, s in enumerate(schemas)])
def test_jsonschema_roundtrip(input_schema):
    # Deepcopy to avoid mutation during test
    schema = copy.deepcopy(input_schema)

    # Step 1: Use parser to get parameter objects (algorithm below)
    # Extract params from top-level props, required, etc.
    parameters = []
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    for name, prop_schema in properties.items():
        param = parse_json_schema_to_parameter(
            name=name,
            prop_schema=prop_schema,
            required=name in required
        )
        parameters.append(param)

    # make a param set 
    params = list(parameters) 

    # Step 2: Convert back to schema
    regenerated = _parameters_to_json_schema(params)
    # regenerated.pop("additionalProperties", None)   # this is needed by litellm

    schema_ = copy.deepcopy(schema)
    regenerated_ = copy.deepcopy(regenerated)
    schema_.pop("$schema", None)
    regenerated_.pop("$schema", None)

    ######## INCASE YOU WANT TO DEBUG ########
    # print(json.dumps(schema_, indent=2))
    # print(json.dumps(regenerated_, indent=2))
    ##########################################

    # Step 3: Deep equality check
    assert deep_equal(schema_, regenerated_), "Schemas are not deeply equal"
