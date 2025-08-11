#!/usr/bin/env python3
"""
Test to verify that no extra print statements are output during normal railtracks usage.
This test validates the fix for issue #514.
"""

import io
import sys
import railtracks as rt


def test_no_extra_print_statements():
    """Test that running a simple function node doesn't produce debug print statements."""
    
    def example_function(x: int, y: int) -> float:
        return x + y

    function = rt.function_node(example_function)
    
    # Capture stdout to check what gets printed
    captured_output = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = captured_output
    
    try:
        result = rt.call_sync(function, 5, 10)
        assert result == 15  # Verify the function works correctly
    finally:
        sys.stdout = original_stdout
    
    # Get the captured output
    output = captured_output.getvalue()
    
    # Check that problematic debug statements are NOT present
    assert "--------------------------------- None" not in output, f"Found debug output in: {output}"
    assert "Creating new session" not in output, f"Found debug output in: {output}"
    assert "register_globals" not in output, f"Found debug output in: {output}"
    
    print("✓ No extra print statements found - fix verified!")


if __name__ == "__main__":
    test_no_extra_print_statements()