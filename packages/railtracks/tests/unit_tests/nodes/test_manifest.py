import pytest

from railtracks.nodes.manifest import ToolManifest

# ================= START ToolManifest tests ============

class DummyParameter:
    def __init__(self, name):
        self.name = name

@pytest.fixture
def single_parameter():
    return DummyParameter("param1")

@pytest.fixture
def multiple_parameters():
    return [DummyParameter("param1"), DummyParameter("param2")]

def test_tool_manifest_with_no_parameters():
    description = "Test tool"
    manifest = ToolManifest(description)
    assert manifest.description == description
    assert manifest.parameters == []

def test_tool_manifest_with_single_parameter(single_parameter):
    description = "Test tool"
    manifest = ToolManifest(description, parameters=[single_parameter])
    assert manifest.description == description
    assert manifest.parameters == [single_parameter]

def test_tool_manifest_with_multiple_parameters(multiple_parameters):
    description = "Test tool with many params"
    manifest = ToolManifest(description, parameters=multiple_parameters)
    assert manifest.description == description
    assert manifest.parameters == multiple_parameters

def test_tool_manifest_with_iterable_parameter(single_parameter):
    description = "Iterable test"
    param_gen = (param for param in [single_parameter])
    manifest = ToolManifest(description, parameters=param_gen)
    assert manifest.description == description
    assert manifest.parameters == [single_parameter]

def test_tool_manifest_with_parameters_none():
    description = "Parameters none test"
    manifest = ToolManifest(description, parameters=None)
    assert manifest.description == description
    assert manifest.parameters == []

# ================ END ToolManifest tests ===============