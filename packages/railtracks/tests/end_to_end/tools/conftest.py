import pytest
import json
import os 

def load_json_schemas():
    with open(os.path.join(os.path.dirname(__file__), "test_schemas_for_tools.json")) as f:
        data = json.load(f)
    return data

def normalize_type_spec(obj):
    """
    Normalize type specifications to a canonical form for comparison.
    Converts both 'type': [types...] and 'anyOf': [{'type': t}, ...] to the same representation.
    Returns a set of types if this is a type specification, otherwise returns None.
    """
    if isinstance(obj, dict):
        # Case 1: {"type": ["object", "null"]} or {"type": "object"}
        if "type" in obj and len(obj) == 1:
            type_val = obj["type"]
            if isinstance(type_val, list):
                return frozenset(type_val)
            else:
                return frozenset([type_val])
        
        # Case 2: {"anyOf": [{"type": "object"}, {"type": "null"}]}
        if "anyOf" in obj and len(obj) == 1:
            any_of = obj["anyOf"]
            if isinstance(any_of, list):
                types = []
                for item in any_of:
                    if isinstance(item, dict) and "type" in item and len(item) == 1:
                        types.append(item["type"])
                    else:
                        # Not a simple type spec
                        return None
                return frozenset(types)
    
    return None

def deep_equal(a, b, parent_key=None):
    # Check if both are type specifications that can be normalized
    a_types = normalize_type_spec(a)
    b_types = normalize_type_spec(b)
    
    if a_types is not None and b_types is not None:
        if a_types == b_types:
            return True
        else:
            print(f"[Type spec mismatch] at {parent_key}: {a_types} != {b_types}")
            return False
    
    if isinstance(a, dict) and isinstance(b, dict):
        a_filtered = {k: v for k, v in a.items() if k != "additionalProperties"}
        b_filtered = {k: v for k, v in b.items() if k != "additionalProperties"}

        if set(a_filtered.keys()) != set(b_filtered.keys()):
            print(f"[Dict keys mismatch] at {parent_key}: {set(a_filtered.keys())} != {set(b_filtered.keys())}")
            return False

        for k in a_filtered:
            if not deep_equal(a_filtered[k], b_filtered[k], k):
                print(f"[Dict value mismatch] at key: {k}")
                return False
        return True

    elif isinstance(a, list) and isinstance(b, list):
        if parent_key == "required":
            if set(a) != set(b):
                print(f"[Unordered list mismatch] at {parent_key}: {a} != {b}")
                return False
            return True
        else:
            if len(a) != len(b):
                print(f"[List length mismatch] at {parent_key}: {len(a)} != {len(b)}")
                return False
            for i, (x, y) in enumerate(zip(a, b)):
                if not deep_equal(x, y, f"{parent_key}[{i}]" if parent_key else f"[{i}]"):
                    print(f"[List element mismatch] at {parent_key}[{i}]: {x} != {y}")
                    return False
            return True

    else:
        if a != b:
            print(f"[Value mismatch] at {parent_key}: {a} != {b}")
        return a == b

    
@pytest.fixture(scope="module")
def json_schemas():
    return load_json_schemas()