import json
from typing import List

# Import your Parameter classes and the conversion function
# Adjust these import paths based on your project structure
from railtracks.llm.tools.parameters import Parameter, SimpleParameter, ArrayParameter, ObjectParameter, UnionParameter, RefParameter
from railtracks.llm.models._litellm_wrapper import _parameters_to_json_schema  # adjust this import to your actual location


def main():
    # Example default parameters
    param_name = SimpleParameter(name="username", param_type="string", description="User's login name", required=True)
    param_age = SimpleParameter(name="age", param_type="integer", description="User's age", required=False, default=18)

    # Example array parameter: array of strings
    inside_array = SimpleParameter(name="tag_item", param_type="string")
    array_param = ArrayParameter(
        name="tags",
        description="List of tags",
        items=inside_array,
        required=False,
        max_items=10,
    )

    # Example object parameter with properties
    obj_param = ObjectParameter(
        name="address",
        description="User address",
        required=True,
        properties=[
            SimpleParameter(name="street", param_type="string", description="Street address"),
            SimpleParameter(name="city", param_type="string", description="City name", required=True),
            SimpleParameter(name="postal_code", param_type="string", description="Postal code")
        ],
        additional_properties=False
    )

    # Example union parameter: string or null
    union_param = UnionParameter(
        name="middle_name",
        description="User middle name or null",
        options=[
            SimpleParameter(name="middle_name", param_type="string", description="User middle name"),
            SimpleParameter(name="middle_name", param_type="null", description="User param type is null")
        ],
        required=False,
        default=None
    )

    # Example ref parameter
    ref_param = RefParameter(
        name="custom_type",
        description="Reference to custom schema",
        required=True,
        ref_path="#/components/schemas/CustomType"
    )

    all_params: List[Parameter] = [
        param_name,
        param_age,
        array_param,
        obj_param,
        union_param,
        ref_param,
    ]

    json_schema = _parameters_to_json_schema(all_params)
    print(json.dumps(json_schema, indent=4))


if __name__ == "__main__":
    main()