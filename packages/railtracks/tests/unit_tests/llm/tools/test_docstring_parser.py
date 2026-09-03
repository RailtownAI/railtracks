"""
Tests for the docstring_parser module.

This module contains tests for the docstring parsing utilities in the
railtracks.llm.tools.docstring_parser module.
"""

from railtracks.llm.tools.docstring_parser import (
    extract_args_section,
    extract_main_description,
    parse_args_section,
    parse_docstring_args,
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

    def test_param_description_on_next_line(self):
        """A parameter whose description starts on the next line stays in the section."""
        docstring = """
        This is a docstring.

        Args:
            param1:
                Description of param1.
            param2: Description of param2.

        Returns:
            The return value.
        """
        result = extract_args_section(docstring)
        assert "param1:" in result
        assert "Description of param1." in result
        assert "param2: Description of param2." in result
        assert "The return value." not in result

    def test_description_ending_in_colon(self):
        """A description that ends in a colon does not end the section."""
        docstring = """
        Args:
            mapping: Maps keys to values as follows:
                a -> b
            other: Another parameter.
        """
        result = extract_args_section(docstring)
        assert "mapping: Maps keys to values as follows:" in result
        assert "other: Another parameter." in result

    def test_empty_args_section(self):
        """An empty Args section does not absorb the section that follows it."""
        docstring = """Returns a list of available currencies.
        Args:
        Returns:
            List[str]: A list of available currencies.
        """
        assert extract_args_section(docstring).strip() == ""

    def test_section_header_at_parameter_indent(self):
        """A following section is recognised even at parameter indentation."""
        docstring = """
        Args:
            param1: Description of param1.
        Returns:
            The return value.
        """
        result = extract_args_section(docstring)
        assert "param1: Description of param1." in result
        assert "The return value." not in result


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

    def test_continuation_line_starting_with_word(self):
        """Continuation lines starting with ``Word:`` are not new parameters."""
        args_section = """
            headers: Optional dict of extra headers.
                Note: keys are case-insensitive.
            timeout: Optional request timeout.
        """
        expected = {
            "headers": "Optional dict of extra headers. Note: keys are case-insensitive.",
            "timeout": "Optional request timeout.",
        }
        assert parse_args_section(args_section) == expected

    def test_shallower_param_is_not_swallowed(self):
        """A parameter indented less than the first one still starts a new entry."""
        args_section = """
                headers: extra headers
            timeout: request timeout
        """
        expected = {
            "headers": "extra headers",
            "timeout": "request timeout",
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

    def test_continuation_line_starting_with_word(self):
        """Continuation lines starting with ``Word:`` are kept as description text."""
        docstring = """
        Fetches a URL.

        Args:
            headers: Optional dict of extra headers.
                Note: keys are case-insensitive.

        Returns:
            The response body.
        """
        expected = {
            "headers": "Optional dict of extra headers. Note: keys are case-insensitive.",
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

    def test_description_starting_on_next_line(self):
        """Descriptions starting on the line after the parameter are parsed."""
        docstring = """
        Fetches a URL.

        Args:
            headers:
                Optional dict of extra headers.
            timeout: Optional request timeout.

        Returns:
            The response body.
        """
        expected = {
            "headers": "Optional dict of extra headers.",
            "timeout": "Optional request timeout.",
        }
        assert parse_docstring_args(docstring) == expected

    def test_description_ending_in_colon(self):
        """A description ending in a colon does not truncate the Args section."""
        docstring = """
        Args:
            mapping: Maps keys to values as follows:
                a -> b
            other: Another parameter.
        """
        expected = {
            "mapping": "Maps keys to values as follows: a -> b",
            "other": "Another parameter.",
        }
        assert parse_docstring_args(docstring) == expected

    def test_empty_args_section(self):
        """An empty Args section yields no parameters."""
        docstring = """Returns a list of available currencies.
        Args:
        Returns:
            List[str]: A list of available currencies.
        """
        assert parse_docstring_args(docstring) == {}


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
