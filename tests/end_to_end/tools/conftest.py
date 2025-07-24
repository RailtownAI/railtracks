import pytest
import  json
import os 

def load_json_schemas():
    with open(os.path.join(os.path.dirname(__file__), "test_schemas_for_tools.json")) as f:
        data = json.load(f)
    return data

def deep_equal(a, b, parent_key=None):
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
                if not deep_equal(x, y):
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