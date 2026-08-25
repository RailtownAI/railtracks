"""
Docstring parsing utilities.

This module contains functions for parsing Python docstrings to extract
parameter descriptions and other documentation.
"""

import re
from typing import Dict

from .parameters import Parameter, ParameterType

# Section headers that can follow an "Args:" block and therefore end it.
_SECTION_HEADERS = frozenset(
    {
        "args",
        "arguments",
        "attributes",
        "example",
        "examples",
        "keyword args",
        "keyword arguments",
        "methods",
        "note",
        "notes",
        "other parameters",
        "parameters",
        "raises",
        "references",
        "return",
        "returns",
        "see also",
        "todo",
        "warning",
        "warnings",
        "warns",
        "yield",
        "yields",
    }
)


# HELPER
def _indent_of(line: str) -> int:
    """Returns the number of leading whitespace characters in a line."""
    return len(line) - len(line.lstrip())


# HELPER
def _is_section_header(line: str) -> bool:
    """Returns whether a line is a bare section header, e.g. ``Returns:``."""
    stripped = line.strip()
    return stripped.endswith(":") and stripped[:-1].strip().lower() in _SECTION_HEADERS


# HELPER
def param_from_python_type(
    py_type, name: str = "", description: str | None = None, required: bool = True
) -> Parameter:
    mapped_type = ParameterType.from_python_type(py_type).value
    return Parameter(
        name=name, param_type=mapped_type, description=description, required=required
    )


def parse_docstring_args(docstring: str) -> Dict[str, str]:
    """
    Parses the 'Args:' section from a docstring.
    Returns a dictionary mapping parameter names to their descriptions.

    Args:
        docstring: The docstring to parse.

    Returns:
        A dictionary mapping parameter names to their descriptions.
    """
    if not docstring:
        return {}

    # Extract the Args section
    args_section = extract_args_section(docstring)
    if not args_section:
        return {}

    # Parse the arguments and their descriptions
    return parse_args_section(args_section)


def extract_args_section(docstring: str) -> str:
    """
    Extracts the 'Args:' section from a docstring.

    Args:
        docstring: The docstring to extract from.

    Returns:
        The extracted 'Args:' section as a string, or an empty string if not found.
    """
    args_lines = []
    in_args_section = False
    body_indent = None

    # Find the Args: section
    for line in docstring.splitlines():
        if not in_args_section:
            if line.strip().startswith("Args:"):
                in_args_section = True
            # Skip everything up to and including the "Args:" line itself
            continue

        # Blank lines never end the section
        if not line.strip():
            args_lines.append(line)
            continue

        indent = _indent_of(line)

        # The next section is indented less than the parameters, or named like one.
        if (body_indent is None or indent <= body_indent) and _is_section_header(line):
            break

        if body_indent is None:
            # The first parameter line sets the indentation of the section body
            body_indent = indent
        elif indent < body_indent:
            break

        # Add the line to our args section
        args_lines.append(line)

    return "".join(line + "\n" for line in args_lines)


def parse_args_section(args_section: str) -> Dict[str, str]:
    """
    Parses an 'Args:' section into a dictionary of parameter names and descriptions.

    Args:
        args_section: The extracted 'Args:' section text.

    Returns:
        A dictionary mapping parameter names to their descriptions.
    """
    # Regular expression to match parameter definitions
    # This handles both formats:
    # - param_name: Description
    # - param_name (type): Description
    # The description may be empty, meaning it starts on the following line.
    pattern = re.compile(r"^(\s*)(\w+)(?:\s*\([^)]+\))?:\s*(.*)$")

    arg_descriptions = {}
    current_arg = None
    current_description = []
    param_indent = None

    for line in args_section.splitlines():
        # Skip empty lines
        if not line.strip():
            continue

        # Check if this is a new parameter definition
        match = pattern.match(line)
        if match:
            indent = len(match.group(1))
            if param_indent is None:
                param_indent = indent

            if indent > param_indent:
                # A deeper-indented "Note:"-style line is continuation text.
                if current_arg:
                    current_description.append(line.strip())
                continue

            # A shallower match means the anchor came from a continuation line.
            param_indent = indent

            # If we were processing a previous parameter, save it
            if current_arg and current_description:
                arg_descriptions[current_arg] = " ".join(current_description).strip()

            # Start a new parameter; an empty description continues on the next line.
            arg_name = match.group(2)
            arg_desc = match.group(3).strip()
            current_arg = arg_name
            current_description = [arg_desc] if arg_desc else []
        elif current_arg:
            # This is a continuation of the previous parameter's description
            current_description.append(line.strip())

    if current_arg and current_description:
        arg_descriptions[current_arg] = " ".join(current_description).strip()

    return arg_descriptions


def extract_main_description(docstring: str) -> str:
    """
    Extracts the main description from a docstring (before any sections like Args:, Returns:, etc.)

    Args:
        docstring: The docstring to extract from.

    Returns:
        The main description as a string.
    """
    if not docstring:
        return ""

    # Split the docstring into lines
    lines = docstring.splitlines()

    # Collect lines until we hit a section marker (like "Args:")
    main_description = []
    for line in lines:
        if (
            line.strip()
            and line.strip().endswith(":")
            and not line.strip().startswith(" ")
        ):
            break
        main_description.append(line)

    return "\n".join(main_description).strip()
