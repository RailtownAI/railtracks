"""
Tests for the docstring_parser module.

This module contains tests for the docstring parsing utilities in the
railtracks.llm.tools.docstring_parser module.
"""

from railtracks.llm.tools.docstring_parser import (
    parse_docstring_args,
    extract_args_section,
    parse_args_section,
    extract_main_description,
)


class TestExtractMainDescription:
    """Tests for the extract_main_description function."""

    def test_empty_docstring(self):
        """Test that an empty docstring returns an empty string."""
        assert extract_main_description("") == ""
        assert extract_main_description(None) == ""

    def test_simple_description(self):
        """Test extracting a simple description."""
        docstring = """This is a simple description."""
        assert extract_main_description(docstring) == "This is a simple description."

    def test_multiline_description(self):
        """Test extracting a multiline description."""
        docstring = """This is a multiline
        description that spans
        multiple lines."""
        expected = """This is a multiline
        description that spans
        multiple lines."""
        assert extract_main_description(docstring) == expected

    def test_description_with_sections(self):
        """Test extracting a description that has sections."""
        docstring = """This is the main description.

        Args:
            param1: Description of param1.
            
        Returns:
            The return value.
        """
        assert extract_main_description(docstring) == "This is the main description."


class TestExtractArgsSection:
    """Tests for the extract_args_section function."""

    def test_no_args_section(self):
        """Test a docstring without an Args section."""
        docstring = """This is a docstring without an Args section."""
        assert extract_args_section(docstring) == ""

    def test_simple_args_section(self):
        """Test extracting a simple Args section."""
        docstring = """
        This is a docstring.
        
        Args:
            param1: Description of param1.
            param2: Description of param2.
        
        Returns:
            The return value.
        """
        # The actual output includes the indentation and newlines
        result = extract_args_section(docstring)
        assert "param1: Description of param1." in result
        assert "param2: Description of param2." in result

    def test_args_section_with_types(self):
        """Test extracting an Args section with type annotations."""
        docstring = """
        This is a docstring.
        Args:
            param1 (str): Description of param1.
            param2 (int): Description of param2.
        """
        # The actual output includes the indentation and newlines
        result = extract_args_section(docstring)
        assert "param1 (str): Description of param1." in result
        assert "param2 (int): Description of param2." in result


class TestParseArgsSection:
    """Tests for the parse_args_section function."""

    def test_simple_args(self):
        """Test parsing simple Args."""
        args_section = """
            param1: Description of param1.
            param2: Description of param2.
        """
        expected = {
            "param1": "Description of param1.",
            "param2": "Description of param2.",
        }
        assert parse_args_section(args_section) == expected

    def test_args_with_types(self):
        """Test parsing Args with type annotations."""
        args_section = """
            param1 (str): Description of param1.
            param2 (int): Description of param2.
        """
        expected = {
            "param1": "Description of param1.",
            "param2": "Description of param2.",
        }
        assert parse_args_section(args_section) == expected

    def test_multiline_descriptions(self):
        """Test parsing Args with multiline descriptions."""
        args_section = """
            param1: Description of param1
                that spans multiple lines.
            param2: Description of param2.
        """
        expected = {
            "param1": "Description of param1 that spans multiple lines.",
            "param2": "Description of param2.",
        }
        assert parse_args_section(args_section) == expected


class TestParseDocstringArgs:
    """Tests for the parse_docstring_args function."""

    def test_empty_docstring(self):
        """Test parsing an empty docstring."""
        assert parse_docstring_args("") == {}
        assert parse_docstring_args(None) == {}

    def test_docstring_without_args(self):
        """Test parsing a docstring without Args section."""
        docstring = """This is a docstring without an Args section."""
        assert parse_docstring_args(docstring) == {}

    def test_simple_docstring(self):
        """Test parsing a simple docstring with Args."""
        docstring = """
        This is a docstring.
        
        Args:
            param1: Description of param1.
            param2: Description of param2.
        
        Returns:
            The return value.
        """
        expected = {
            "param1": "Description of param1.",
            "param2": "Description of param2.",
        }
        assert parse_docstring_args(docstring) == expected

    def test_complex_docstring(self):
        """Test parsing a complex docstring with various sections."""
        docstring = """
        This is a complex docstring.
        
        It has multiple paragraphs in the description.
        
        Args:
            param1 (str): Description of param1
                that spans multiple lines.
            param2 (int): Description of param2.
        
        Returns:
            The return value.
            
        Raises:
            ValueError: If something goes wrong.
        """
        expected = {
            "param1": "Description of param1 that spans multiple lines.",
            "param2": "Description of param2.",
        }
        assert parse_docstring_args(docstring) == expected

    def test_real_world_example(self):
        """Test parsing a real-world docstring example."""
        docstring = """
        Creates a new instance of a parameter object.

        Args:
            name: The name of the parameter.
            param_type: The type of the parameter.
            description: A description of the parameter.
            required: Whether the parameter is required. Defaults to True.
        """
        expected = {
            "name": "The name of the parameter.",
            "param_type": "The type of the parameter.",
            "description": "A description of the parameter.",
            "required": "Whether the parameter is required. Defaults to True.",
        }
        assert parse_docstring_args(docstring) == expected


class TestEdgeCases:
    """Tests for edge cases in docstring parsing."""

    def test_malformed_args_section(self):
        """Test parsing a malformed Args section."""
        docstring = """
        Args:
            This is not a proper parameter definition.
            param1: This is a proper one.
        """
        # Should only extract the properly formatted parameter
        expected = {"param1": "This is a proper one."}
        assert parse_docstring_args(docstring) == expected
