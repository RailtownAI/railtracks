"""Test that important classes are available at the root import level."""


def test_tool_manifest_root_import():
    """Test that ToolManifest can be imported from the root railtracks module."""
    import railtracks as rt
    
    # Test that ToolManifest is available at root level
    assert hasattr(rt, 'ToolManifest'), "ToolManifest should be available as rt.ToolManifest"
    
    # Test that we can create an instance
    manifest = rt.ToolManifest("Test description")
    assert manifest.description == "Test description"
    assert manifest.parameters == []


def test_tool_manifest_with_parameters():
    """Test that ToolManifest works properly when imported from root."""
    import railtracks as rt
    from railtracks.llm import Parameter
    
    param = Parameter(
        name="test_param",
        param_type="string",
        description="A test parameter"
    )
    
    manifest = rt.ToolManifest("Test description", [param])
    assert manifest.description == "Test description"
    assert len(manifest.parameters) == 1
    assert manifest.parameters[0].name == "test_param"


def test_tool_manifest_backward_compatibility():
    """Test that the old import method still works."""
    from railtracks.nodes.manifest import ToolManifest
    
    manifest = ToolManifest("Test description")
    assert manifest.description == "Test description"
    assert manifest.parameters == []