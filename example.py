from railtracks.llm.tools.parameters import DefaultParameter, UnionParameter

# Test DefaultParameter
param = DefaultParameter(
    name="test_param",
    param_type="string",
    description="Test parameter",
    required=True,
    default="default_value",
)

print(param.to_json_schema())

x = {
    "type": "object",
    "properties": {
        "page": {
            "type": "number",
            "default": 1,
            "description": "The page number of the result set to fetch.",
        },
        "page_size": {
            "type": "number",
            "default": 100,
            "description": "The number of records to return per page (maximum 100).",
        },
        "total_required": {
            "type": "boolean",
            "description": "Indicates whether the response should include the total count of items.",
        },
    },
    "additionalProperties": False,
    "$schema": "http://json-schema.org/draft-07/schema#",
}


# ==========
# Test UnionParameter
options = [
    DefaultParameter(
        name="page",
        param_type="number",
        description="The page number of the result set to fetch.",
        required=True,
        default=1,
    ),
    DefaultParameter(
        name="page_size",
        param_type="number",
        description="The number of records to return per page (maximum 100).",
        required=True,
        default=100,
    ),
    DefaultParameter(
        name="total_required",
        param_type="boolean",
        description="Indicates whether the response should include the total count of items.",
        required=True,
    )
]

param = UnionParameter(
    name="pages",
    options=options,
    description="The page number of the result set to fetch.",
    required=True,
)

print(param.to_json_schema())