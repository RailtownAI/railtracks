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
        "Arguments",
        "Attributes",
        "Parameters",
        "Raises",
        "Returns",
        "Yields",
    }
)

# Google-style headers that open a parameter block.
_GOOGLE_ARGS_HEADERS = ("Args:", "Arguments:", "Parameters:")

# NumPy section names, recognised as headers when underlined or colon-terminated.
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

_NUMPY_PARAM_HEADERS = ("Parameters", "Other Parameters")

# Sphinx info-field names that describe a parameter.
_REST_PARAM_FIELDS = "param|parameter|arg|argument|key|keyword"
# ":param name: desc" or ":param type name: desc", matched against a stripped line.
_REST_PARAM_PATTERN = re.compile(
    rf"^:(?:{_REST_PARAM_FIELDS})\s+(?:[\w.~\[\],| ]+?\s+)?(\w+)\s*:\s*(.*)$"
)
# Any Sphinx info field, e.g. ":param x:", ":type x:", ":returns:".
_REST_FIELD_PATTERN = re.compile(
    rf"^:(?:{_REST_PARAM_FIELDS}|type|returns?|rtype|raises?|except|exception"
    r"|yields?|var|ivar|cvar|vartype|meta|kwarg)\b"
)
# An inline role such as ":class:`Foo`", which is prose rather than a field.
_REST_ROLE_PATTERN = re.compile(r"^:[\w.+-]+(?::[\w.+-]+)*:`")


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
    stripped = line.strip()
    return bool(_REST_FIELD_PATTERN.match(stripped)) and not (
        _REST_ROLE_PATTERN.match(stripped)
    )


# HELPER
def _is_underline(line: str) -> bool:
    """Returns whether a line is a run of dashes or equals signs."""
    return set(line.strip()) in ({"-"}, {"="})


# HELPER
def _is_underlined_heading(lines: list[str], index: int) -> bool:
    """Returns whether ``lines[index]`` is text followed by an underline."""
    stripped = lines[index].strip()
    return (
        bool(stripped)
        and not _is_underline(stripped)
        and index + 1 < len(lines)
        and _is_underline(lines[index + 1])
    )


# HELPER
def _is_numpy_section_header(lines: list[str], index: int) -> bool:
    """Returns whether ``lines[index]`` is an underlined NumPy section name.

    A prose line that happens to read ``Notes`` does not qualify.
    """
    return lines[index].strip().rstrip(":") in _NUMPY_SECTION_NAMES and (
        _is_underlined_heading(lines, index)
    )


# HELPER
def _is_google_args_header(lines: list[str], index: int) -> bool:
    """Returns whether ``lines[index]`` opens a Google-style parameter block.

    A header that only labels reST fields (``Parameters:`` then ``:param x:``)
    does not qualify.
    """
    if not lines[index].strip().startswith(_GOOGLE_ARGS_HEADERS):
        return False
    if _is_numpy_section_header(lines, index):
        return False
    first_body_line = next((line for line in lines[index + 1 :] if line.strip()), "")
    return not _is_rest_field(first_body_line)


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
    Parses parameter descriptions from a Google, NumPy, or reST/Sphinx style
    docstring. Styles are tried in that order and the first non-empty result
    wins.

    Args:
        docstring: The docstring to parse.

    Returns:
        A dictionary mapping parameter names to their descriptions.
    """
    if not docstring:
        return {}

    # Google style
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

    Google ``Args:`` headers each count once, NumPy ``Parameters`` and
    ``Other Parameters`` together count as one section, and any number of reST
    parameter fields counts as a single reST section.

    Args:
        docstring: The docstring to inspect.

    Returns:
        The number of parameter sections found.
    """
    if not docstring:
        return 0

    lines = docstring.splitlines()

    sections = sum(
        1 for index in range(len(lines)) if _is_google_args_header(lines, index)
    )
    if any(
        line.strip().rstrip(":") in _NUMPY_PARAM_HEADERS
        and _is_numpy_section_header(lines, index)
        for index, line in enumerate(lines)
    ):
        sections += 1
    if any(_REST_PARAM_PATTERN.match(line.strip()) for line in lines):
        sections += 1

    return sections


def extract_args_section(docstring: str) -> str:
    """
    Extracts the Google-style 'Args:' section from a docstring. 'Arguments:'
    and 'Parameters:' are accepted as aliases.

    Args:
        docstring: The docstring to extract from.

    Returns:
        The extracted 'Args:' section as a string, or an empty string if not found.
    """
    args_lines = []
    in_args_section = False
    body_indent = None
    lines = docstring.splitlines()

    # Find the Args: section
    for index, line in enumerate(lines):
        if not in_args_section:
            if _is_google_args_header(lines, index):
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

    header_indent: int | None = None
    for index, line in enumerate(split_lines):
        stripped = line.strip()
        if header_indent is None:
            if stripped.rstrip(":") in _NUMPY_PARAM_HEADERS and (
                _is_numpy_section_header(split_lines, index)
            ):
                header_indent = _indent_of(line)
            continue

        if stripped and _is_underline(stripped):
            continue

        # Other Parameters extends the same parameter block.
        if stripped.rstrip(":") == "Other Parameters":
            continue

        # A heading at the header's indent starts the next section; deeper
        # lines are parameter descriptions.
        if stripped and _indent_of(line) <= header_indent:
            if _is_underlined_heading(split_lines, index) or (
                stripped.endswith(":") and stripped.rstrip(":") in _NUMPY_SECTION_NAMES
            ):
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

    # Deeper-indented matches (e.g. "Note: keep this in mind.") are description text.
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
    Parses reST/Sphinx style parameter fields from a docstring. Accepts every
    Sphinx parameter field name: ':param', ':parameter', ':arg', ':argument',
    ':key', and ':keyword'.

    Args:
        docstring: The docstring to parse.

    Returns:
        A dictionary mapping parameter names to their descriptions.
    """
    arg_descriptions: Dict[str, str] = {}
    current_arg: str | None = None
    current_description: list[str] = []
    field_indent = 0
    after_blank = False

    for line in docstring.splitlines():
        stripped = line.strip()
        if not stripped:
            after_blank = True
            continue
        new_paragraph, after_blank = after_blank, False

        # Check if this is a new parameter field
        match = _REST_PARAM_PATTERN.match(stripped)
        if match:
            # If we were processing a previous parameter, save it
            if current_arg and current_description:
                arg_descriptions[current_arg] = " ".join(current_description).strip()

            # Start a new parameter
            current_arg = match.group(1)
            current_description = [match.group(2).strip()]
            field_indent = _indent_of(line)
        elif (stripped.startswith(":") and not _REST_ROLE_PATTERN.match(stripped)) or (
            new_paragraph and _indent_of(line) <= field_indent
        ):
            # Another field (e.g. ':type:'), or a paragraph not indented under the field, ends it
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
        if stripped and _is_numpy_section_header(lines, index):
            break
        if _is_rest_field(line):
            break
        main_description.append(line)

    return "\n".join(main_description).strip()
