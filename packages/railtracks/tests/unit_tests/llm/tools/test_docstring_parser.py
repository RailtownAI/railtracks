"""
Tests for the docstring_parser module.

This module contains tests for the docstring parsing utilities in the
railtracks.llm.tools.docstring_parser module.
"""

from railtracks.llm.tools.docstring_parser import (
    extract_args_section,
    extract_main_description,
    extract_numpy_args_section,
    parse_args_section,
    parse_docstring_args,
    parse_rest_args_section,
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

    def test_parameter_named_like_a_section(self):
        """A parameter named ``notes`` is not mistaken for a section header."""
        docstring = """
        Args:
            notes:
                Notes attached to the record.
            value: The value.
        """
        expected = {
            "notes": "Notes attached to the record.",
            "value": "The value.",
        }
        assert parse_docstring_args(docstring) == expected

    def test_lowercase_parameter_matching_a_section_name(self):
        """Section headers are matched case-sensitively, so ``args:`` is a parameter."""
        docstring = """
        Args:
            args:
                Positional arguments forwarded to the handler.
            value: The value.
        """
        expected = {
            "args": "Positional arguments forwarded to the handler.",
            "value": "The value.",
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


class TestNumpyArgsSection:
    """Tests for NumPy-style docstring parsing."""

    def test_simple_numpy_docstring(self):
        """Test parsing a simple NumPy-style docstring."""
        docstring = """
        Adds two numbers together.

        Parameters
        ----------
        a : int
            The first number.
        b : int
            The second number.

        Returns
        -------
        int
            The sum of the two numbers.
        """
        expected = {"a": "The first number.", "b": "The second number."}
        assert parse_docstring_args(docstring) == expected

    def test_numpy_main_description(self):
        """Test extracting the main description from a NumPy-style docstring."""
        docstring = """
        Adds two numbers together.

        Parameters
        ----------
        a : int
            The first number.

        Returns
        -------
        int
            The sum.
        """
        assert extract_main_description(docstring) == "Adds two numbers together."

    def test_numpy_with_optional(self):
        """Test parsing NumPy-style parameters marked optional."""
        docstring = """
        Computes a value.

        Parameters
        ----------
        x : float, optional
            The x value. Defaults to 1.0.
        y : float
            The y value.

        Returns
        -------
        float
            The result.
        """
        expected = {
            "x": "The x value. Defaults to 1.0.",
            "y": "The y value.",
        }
        assert parse_docstring_args(docstring) == expected

    def test_no_numpy_parameters_section(self):
        """Test that a docstring without a NumPy Parameters section returns empty."""
        docstring = """This is a docstring without a Parameters section."""
        assert extract_numpy_args_section(docstring) == ""
        assert parse_docstring_args(docstring) == {}


class TestRestArgsSection:
    """Tests for reST/Sphinx-style docstring parsing."""

    def test_simple_rest_docstring(self):
        """Test parsing a simple reST-style docstring."""
        docstring = """
        Adds two numbers together.

        :param a: The first number.
        :param b: The second number.
        :type a: int
        :type b: int
        :returns: The sum of the two numbers.
        :rtype: int
        """
        expected = {"a": "The first number.", "b": "The second number."}
        assert parse_docstring_args(docstring) == expected

    def test_rest_with_typed_params(self):
        """Test parsing reST-style parameters that include types."""
        docstring = """
        Greets a person.

        :param str name: The name to greet.
        :param bool excited: Whether to greet excitedly.
        """
        expected = {
            "name": "The name to greet.",
            "excited": "Whether to greet excitedly.",
        }
        assert parse_docstring_args(docstring) == expected

    def test_rest_with_multiline_description(self):
        """Test parsing reST-style parameters with multiline descriptions."""
        docstring = """
        Computes a value.

        :param x: The x value.
            It can be negative.
        :param y: The y value.
        """
        expected = {"x": "The x value. It can be negative.", "y": "The y value."}
        assert parse_docstring_args(docstring) == expected

    def test_no_rest_params(self):
        """Test that a docstring without :param: fields returns empty."""
        docstring = """This is a docstring without param fields."""
        assert parse_rest_args_section(docstring) == {}
        assert parse_docstring_args(docstring) == {}

    def test_rest_main_description_strips_fields(self):
        """Pure reST docstrings must not ship raw :param lines as the tool description."""
        docstring = """Fetches a URL.

    :param url: The endpoint to hit.
    :type url: str
    :returns: The body.
"""
        assert extract_main_description(docstring) == "Fetches a URL."
        assert parse_docstring_args(docstring) == {"url": "The endpoint to hit."}


class TestFirstMatchStyleSelection:
    """Regression tests for non-destructive first-match parsing (Google → NumPy → reST)."""

    def test_google_wins_over_numpy_without_merging(self):
        """Mixed Google+NumPy docstrings return only Google args (no blind-merge)."""
        docstring = """
        Do something.

        Args:
            a: google arg

        Parameters
        ----------
        b : int
            numpy arg
        """
        assert parse_docstring_args(docstring) == {"a": "google arg"}

    def test_google_args_section_stops_at_numpy_header(self):
        """Google Args: extraction must not swallow a following NumPy Parameters block."""
        docstring = """
        Args:
            a: google

        Parameters
        ----------
        b : int
            numpy
        """
        section = extract_args_section(docstring)
        assert "a: google" in section
        assert "numpy" not in section
        assert "Parameters" not in section
        assert parse_docstring_args(docstring) == {"a": "google"}

    def test_numpy_used_when_no_google_args(self):
        """NumPy is selected when Google Args is absent."""
        docstring = """
        Do something.

        Parameters
        ----------
        x : int
            The x value
        """
        assert parse_docstring_args(docstring) == {"x": "The x value"}

    def test_rest_used_when_no_google_or_numpy(self):
        """reST is selected when Google and NumPy sections are absent."""
        docstring = """
        Do something.

        :param y: The y value.
        """
        assert parse_docstring_args(docstring) == {"y": "The y value."}


class TestParsingRegressions:
    """Regression tests for non-destructive parsing of mixed-style content."""

    def test_google_indented_field_does_not_truncate_args(self):
        """An indented ``:field:`` line inside Args is continuation text."""
        docstring = (
            "Do a thing.\n\nArgs:\n    a: first\n    :note: careful\n    b: second"
        )
        assert parse_docstring_args(docstring) == {
            "a": "first :note: careful",
            "b": "second",
        }

    def test_google_dashes_line_does_not_truncate_args(self):
        """A dashes-only line inside Args does not end the section."""
        docstring = "Do a thing.\n\nArgs:\n    a: first\n    ---\n    b: second"
        assert parse_docstring_args(docstring) == {"a": "first ---", "b": "second"}

    def test_google_prose_with_dashes_kept_in_main_description(self):
        """A prose title followed by dashes in a Google docstring is kept."""
        docstring = (
            "Summary line.\n\nDetails\n-------\nmore prose\n\nArgs:\n    x: the x"
        )
        expected = "Summary line.\n\nDetails\n-------\nmore prose"
        assert extract_main_description(docstring) == expected

    def test_google_role_line_kept_in_main_description(self):
        """A role line at the start of a paragraph is not treated as reST."""
        docstring = (
            "Summary.\n\n:class:`Foo` is the entry point.\n\nArgs:\n    x: the x"
        )
        assert (
            extract_main_description(docstring)
            == "Summary.\n\n:class:`Foo` is the entry point."
        )

    def test_numpy_indented_note_is_continuation(self):
        """An indented ``Note:`` line is description text, not a parameter."""
        docstring = (
            "Computes a value.\n\n"
            "Parameters\n"
            "----------\n"
            "x : int\n"
            "    the x value.\n"
            "    Note: keep this in mind.\n"
        )
        assert parse_docstring_args(docstring) == {
            "x": "the x value. Note: keep this in mind."
        }

    def test_numpy_grouped_untyped_and_variadic_params(self):
        """Grouped, untyped, and variadic numpydoc parameters are supported."""
        docstring = (
            "Does things.\n\n"
            "Parameters\n"
            "----------\n"
            "x, y : int\n"
            "    Both numbers.\n"
            "z\n"
            "    An untyped number.\n"
            "*args : tuple\n"
            "    Extra values.\n"
            "**kwargs : dict\n"
            "    Extra keyword values.\n"
        )
        assert parse_docstring_args(docstring) == {
            "x": "Both numbers.",
            "y": "Both numbers.",
            "z": "An untyped number.",
            "args": "Extra values.",
            "kwargs": "Extra keyword values.",
        }

    def test_numpy_other_parameters_only(self):
        """An 'Other Parameters' section is recognized without 'Parameters'."""
        docstring = (
            "Does things.\n\n"
            "Other Parameters\n"
            "----------------\n"
            "y : int\n"
            "    The y value.\n"
        )
        assert parse_docstring_args(docstring) == {"y": "The y value."}

    def test_numpy_examples_block_not_parsed_as_parameter(self):
        """A colon-style 'Examples:' header ends the parameters section."""
        docstring = (
            "Does things.\n\n"
            "Parameters\n"
            "----------\n"
            "x : int\n"
            "    The x value.\n\n"
            "Examples:\n"
            "    foo(1)\n"
        )
        assert parse_docstring_args(docstring) == {"x": "The x value."}

    def test_rest_subscripted_and_dotted_types(self):
        """reST type annotations with brackets or dots are not skipped."""
        docstring = (
            "Fetches things.\n\n"
            ":param List[int] items: The items to fetch.\n"
            ":param module.Type value: The value to use.\n"
        )
        assert parse_docstring_args(docstring) == {
            "items": "The items to fetch.",
            "value": "The value to use.",
        }
