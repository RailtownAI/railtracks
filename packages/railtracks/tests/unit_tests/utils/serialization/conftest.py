# test_serialization/conftest.py

import pytest
from types import SimpleNamespace

@pytest.fixture
def fake_stamp():
    # Mimic Stamp's required fields
    return SimpleNamespace(time=1.2, step=42, identifier="foo")

@pytest.fixture
def another_fake_stamp():
    return SimpleNamespace(time=2.0, step=2, identifier="id")

@pytest.fixture
def fake_edge(fake_stamp):
    # Edge requires source, target, identifier, stamp, details, parent
    return SimpleNamespace(
        source="src", target="tgt", identifier="edgeid", stamp=fake_stamp,
        details={"stuff": 7}, parent=None
    )

@pytest.fixture
def fake_vertex(fake_stamp):
    return SimpleNamespace(
        identifier="vid", node_type="TYPE", name="Vertex Name", stamp=fake_stamp, details={"a": 1}, parent=None
    )

@pytest.fixture
def fake_request_details():
    return SimpleNamespace(
        model_name="mod", model_provider="prov",
        input="IN", output="OUT", input_tokens=10, output_tokens=5,
        total_cost=0.123, system_fingerprint="FP", latency=100
    )

@pytest.fixture
def fake_latency_details():
    return SimpleNamespace(total_time=1.23)

@pytest.fixture
def fake_message():
    # message.role.value is expected, so mimic with a dummy class
    role = SimpleNamespace(value="user")
    return SimpleNamespace(role=role, content="hi")

@pytest.fixture
def fake_tool_response():
    return SimpleNamespace(identifier="tid", name="tool", result="ok")

@pytest.fixture
def fake_tool_call():
    return SimpleNamespace(identifier="tcid", name="tc", arguments={"x": 1})

@pytest.fixture
def fake_basemodel():
    # Pydantic BaseModel mock, must have model_dump()
    class DummyBaseModel:
        def model_dump(self_inner):
            return {"hello": "world"}
    return DummyBaseModel()