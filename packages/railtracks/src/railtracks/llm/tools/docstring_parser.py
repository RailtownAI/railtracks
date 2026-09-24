"""
Docstring parsing utilities.

This module contains functions for parsing Python docstrings to extract
parameter descriptions and other documentation.
"""

import re
from typing import Dict

from .parameters import Parameter, ParameterType

# Section headers that can follow an "Args:" block and therefore end it. Matched
# case-sensitively, so a lowercase parameter of the same name still parses.
_SECTION_HEADERS = frozenset(
    {
        "Args",
        "Attributes",
        "Raises",
        "Returns",
        "Yields",
    }
)

# Section names that can follow a NumPy-style "Parameters" block. Unlike
# _SECTION_HEADERS, these are matched with or without an underline and with or
# without a trailing colon, so both "Examples" and "Examples:" end the block.
_NUMPY_SECTION_NAMES = frozenset(
    {
        "Parameters",
        "Other Parameters",
        "Attributes",
        "Methods",
        "Returns",
        "Yields",
        "Receives",
        "Raises",
        "Warns",
        "Warnings",
        "See Also",
        "Notes",
        "References",
        "Examples",
    }
)

# reST field-list fields that open a parameter or returns section, e.g.
# ":param name:", ":type name:", ":returns:". Inline roles such as ":func:" are
# ordinary prose that merely happens to start with a colon.
_REST_FIELD_PATTERN = re.compile(
    r"^:(?:param|parameter|type|returns?|rtype|raises?|yields?|keyword|kwarg)\b"
)


# HELPER
def _indent_of(line: str) -> int:
    """Returns the number of leading whitespace characters in a line."""
    return len(line) - len(line.lstrip())


# HELPER
def _is_section_header(line: str) -> bool:
    """Returns whether a line is a bare section header, e.g. ``Returns:``."""
    stripped = line.strip()
    return stripped.endswith(":") and stripped[:-1].strip() in _SECTION_HEADERS


# HELPER
def _is_rest_field(line: str) -> bool:
    """Returns whether a line opens a reST field-list entry, e.g. ``:param x:``."""
    return bool(_REST_FIELD_PATTERN.match(line.strip()))


# HELPER
def _is_numpy_section_header(lines: list[str], index: int) -> bool:
    """Returns whether ``lines[index]`` is a NumPy section header.

    A NumPy header is the section name followed by an underline of dashes, so
    a prose line that happens to read ``Notes`` does not qualify.
    """
    stripped = lines[index].strip()
    if stripped.rstrip(":") not in _NUMPY_SECTION_NAMES:
        return False
    if index + 1 >= len(lines):
        return False
    underline = lines[index + 1].strip()
    return bool(underline) and set(underline) == {"-"}


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
    Parses parameter descriptions from a docstring, supporting Google, NumPy,
    and reST/Sphinx style docstrings. Styles are tried in order and the first
    non-empty result wins, so existing Google docstrings keep parsing exactly
    as before.
    Returns a dictionary mapping parameter names to their descriptions.

    Args:
        docstring: The docstring to parse.

    Returns:
        A dictionary mapping parameter names to their descriptions.
    """
    if not docstring:
        return {}

    # Google style — keep priority for existing users; first match wins.
    args_section = extract_args_section(docstring)
    if args_section:
        parsed = parse_args_section(args_section)
        if parsed:
            return parsed

    # NumPy style
    numpy_section = extract_numpy_args_section(docstring)
    if numpy_section:
        parsed = parse_numpy_args_section(numpy_section)
        if parsed:
            return parsed

    # reST/Sphinx style
    return parse_rest_args_section(docstring)


def count_parameter_sections(docstring: str) -> int:
    """
    Counts the distinct parameter sections in a docstring.

    Google ``Args:`` headers and NumPy ``Parameters``/``Other Parameters``
    headers each count once regardless of how many parameters they hold, and
    any number of reST ``:param`` fields counts as a single reST section.

    Args:
        docstring: The docstring to inspect.

    Returns:
        The number of parameter sections found.
    """
    if not docstring:
        return 0

    lines = docstring.splitlines()

    sections = sum(1 for line in lines if line.strip().startswith("Args:"))
    sections += sum(
        1
        for line in lines
        if line.strip().rstrip(":") in ("Parameters", "Other Parameters")
    )
    if any(re.match(r"^:param(?:eter)?\b", line.strip()) for line in lines):
        sections += 1

    return sections


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


def extract_numpy_args_section(docstring: str) -> str:
    """
    Extracts the 'Parameters' section from a NumPy-style docstring.

    Args:
        docstring: The docstring to extract from.

    Returns:
        The extracted 'Parameters' section as a string, or an empty string if not found.
    """
    params_section = ""
    split_lines = docstring.splitlines()

    in_params_section = False
    for line in split_lines:
        stripped = line.strip()
        if not in_params_section:
            if stripped.rstrip(":") in ("Parameters", "Other Parameters"):
                in_params_section = True
            continue

        # Skip the underline right after the "Parameters" header.
        if stripped and set(stripped) == {"-"}:
            continue

        # Stop at the start of the next section. This covers both underlined
        # NumPy headers and non-underlined ones such as "Examples:".
        if stripped and stripped.rstrip(":") in _NUMPY_SECTION_NAMES:
            break

        params_section += line + "\n"

    return params_section


def parse_numpy_args_section(args_section: str) -> Dict[str, str]:
    """
    Parses a NumPy-style 'Parameters' section into a dictionary of parameter
    names and descriptions. Descriptions come from the lines that follow each
    'name : type' definition.

    Args:
        args_section: The extracted 'Parameters' section text.

    Returns:
        A dictionary mapping parameter names to their descriptions.
    """
    # Parameter definitions may be grouped ("x, y : int"), typed ("x : int"),
    # untyped ("x"), or variadic ("*args", "**kwargs").
    pattern = re.compile(r"^(\s*)(\*{0,2}\w+(?:\s*,\s*\*{0,2}\w+)*)(?:\s*:\s*(.*))?$")

    lines = args_section.splitlines()
    definitions = [
        (i, match) for i, line in enumerate(lines) if (match := pattern.match(line))
    ]
    if not definitions:
        return {}

    # Only lines at the indentation of the first definitions are parameters;
    # deeper-indented lines (e.g. "Note: keep this in mind.") are continuation
    # text of the parameter above them.
    base_indent = min(len(match.group(1)) for _, match in definitions)
    blocks = [
        (i, match) for i, match in definitions if len(match.group(1)) == base_indent
    ]

    arg_descriptions: Dict[str, str] = {}
    for index, (start, match) in enumerate(blocks):
        end = blocks[index + 1][0] if index + 1 < len(blocks) else len(lines)
        description = " ".join(
            line.strip() for line in lines[start + 1 : end] if line.strip()
        )
        for name in match.group(2).split(","):
            arg_descriptions[name.strip().lstrip("*")] = description

    return arg_descriptions


def parse_rest_args_section(docstring: str) -> Dict[str, str]:
    """
    Parses reST/Sphinx style ':param name:' fields from a docstring.

    Args:
        docstring: The docstring to parse.

    Returns:
        A dictionary mapping parameter names to their descriptions.
    """
    pattern = re.compile(
        r"^\s*:(?:param|parameter)\s+(?:[\w.\[\], ]+?\s+)?(\w+)\s*:\s*(.*)$"
    )

    arg_descriptions: Dict[str, str] = {}
    current_arg: str | None = None
    current_description: list[str] = []

    for line in docstring.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Check if this is a new ':param' definition
        match = pattern.match(line)
        if match:
            # If we were processing a previous parameter, save it
            if current_arg and current_description:
                arg_descriptions[current_arg] = " ".join(current_description).strip()

            # Start a new parameter
            current_arg = match.group(1)
            current_description = [match.group(2).strip()]
        elif stripped.startswith(":"):
            # A different reST field (e.g. ':type:' or ':return:') ends the current parameter
            if current_arg and current_description:
                arg_descriptions[current_arg] = " ".join(current_description).strip()
            current_arg = None
            current_description = []
        elif current_arg:
            # This is a continuation of the previous parameter's description
            current_description.append(stripped)

    if current_arg and current_description:
        arg_descriptions[current_arg] = " ".join(current_description).strip()

    return arg_descriptions


def extract_main_description(docstring: str) -> str:
    """
    Extracts the main description from a docstring (before any sections like
    Args:, Parameters:, :param, etc.)

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
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped and stripped.endswith(":"):
            break
        # Only a real NumPy header (name plus dashes underline) ends the
        # description; a prose line that just reads "Notes" does not.
        if stripped and _is_numpy_section_header(lines, index):
            break
        # reST field lists start at the actual fields (":param ...:"); inline
        # roles such as ":func:" are prose and stay in the description.
        if _is_rest_field(line):
            break
        main_description.append(line)

    return "\n".join(main_description).strip()
