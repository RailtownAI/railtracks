"""
Docstring parsing utilities.

This module contains functions for parsing Python docstrings to extract
parameter descriptions and other documentation.
"""

import re
from typing import Dict

from .parameters import Parameter, ParameterType


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
    Parses parameter descriptions from a docstring, supporting Google,
    NumPy, and reST/Sphinx style docstrings.
    Returns a dictionary mapping parameter names to their descriptions.

    Args:
        docstring: The docstring to parse.

    Returns:
        A dictionary mapping parameter names to their descriptions.
    """
    if not docstring:
        return {}

    arg_descriptions = {}

    # Google style
    args_section = extract_args_section(docstring)
    if args_section:
        arg_descriptions.update(parse_args_section(args_section))

    # NumPy style
    numpy_section = extract_numpy_args_section(docstring)
    if numpy_section:
        arg_descriptions.update(parse_numpy_args_section(numpy_section))

    # reST/Sphinx style
    rest_args = parse_rest_args_section(docstring)
    if rest_args:
        arg_descriptions.update(rest_args)

    return arg_descriptions


def extract_args_section(docstring: str) -> str:
    """
    Extracts the 'Args:' section from a docstring.

    Args:
        docstring: The docstring to extract from.

    Returns:
        The extracted 'Args:' section as a string, or an empty string if not found.
    """
    args_section = ""
    split_lines = docstring.splitlines()

    # Find the Args: section
    in_args_section = False
    for i, line in enumerate(split_lines):
        if line.strip().startswith("Args:"):
            in_args_section = True
            # Skip the "Args:" line itself
            continue

        if in_args_section:
            # Check if we've reached another section (e.g., "Returns:")
            if (
                line.strip()
                and line.strip().endswith(":")
                and not line.strip().startswith(" ")
            ):
                break

            # Add the line to our args section
            args_section += line + "\n"

    return args_section


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
    pattern = re.compile(r"^\s*(\w+)(?:\s*\([^)]+\))?:\s*(.+)$")

    arg_descriptions = {}
    current_arg = None
    current_description = []

    for line in args_section.splitlines():
        # Skip empty lines
        if not line.strip():
            continue

        # Check if this is a new parameter definition
        match = pattern.match(line)
        if match:
            # If we were processing a previous parameter, save it
            if current_arg and current_description:
                arg_descriptions[current_arg] = " ".join(current_description).strip()

            # Start a new parameter
            arg_name, arg_desc = match.groups()
            current_arg = arg_name
            current_description = [arg_desc.strip()]
        elif current_arg:
            # This is a continuation of the previous parameter's description
            current_description.append(line.strip())

    if current_arg and current_description:
        arg_descriptions[current_arg] = " ".join(current_description).strip()

    return arg_descriptions


def _is_numpy_section_header(lines: list, i: int) -> bool:
    """Check whether lines[i] is a NumPy-style section header (e.g. 'Parameters')."""
    if not lines[i].strip():
        return False
    j = i + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j < len(lines):
        underline = lines[j].strip()
        if underline and set(underline) == {"-"} and len(underline) >= 3:
            return True
    return False


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
    for i, line in enumerate(split_lines):
        if not in_params_section:
            if line.strip() == "Parameters" and _is_numpy_section_header(
                split_lines, i
            ):
                in_params_section = True
            continue

        # Skip the underline right after the "Parameters" header.
        if line.strip() and set(line.strip()) == {"-"}:
            continue

        # Stop at the start of the next section header.
        if line.strip() and _is_numpy_section_header(split_lines, i):
            break

        params_section += line + "\n"

    return params_section


def parse_numpy_args_section(args_section: str) -> Dict[str, str]:
    """
    Parses a NumPy-style 'Parameters' section into a dictionary of parameter
    names and descriptions. Descriptions come from the indented lines that
    follow each 'name : type' definition.

    Args:
        args_section: The extracted 'Parameters' section text.

    Returns:
        A dictionary mapping parameter names to their descriptions.
    """
    pattern = re.compile(r"^\s*(\w+)\s*:")

    arg_descriptions = {}
    current_arg = None
    current_description = []

    for line in args_section.splitlines():
        # Skip empty lines
        if not line.strip():
            continue

        # Check if this is a new parameter definition
        match = pattern.match(line)
        if match:
            # If we were processing a previous parameter, save it
            if current_arg and current_description:
                arg_descriptions[current_arg] = " ".join(current_description).strip()

            # Start a new parameter
            current_arg = match.group(1)
            current_description = []
        elif current_arg:
            # This is a continuation of the previous parameter's description
            current_description.append(line.strip())

    if current_arg and current_description:
        arg_descriptions[current_arg] = " ".join(current_description).strip()

    return arg_descriptions


def parse_rest_args_section(docstring: str) -> Dict[str, str]:
    """
    Parses reST/Sphinx style ':param name:' fields from a docstring.

    Args:
        docstring: The docstring to parse.

    Returns:
        A dictionary mapping parameter names to their descriptions.
    """
    pattern = re.compile(r"^\s*:(?:param|parameter)\s+(?:(?:\w+)\s+)?(\w+)\s*:\s*(.*)$")

    arg_descriptions = {}
    current_arg = None
    current_description = []

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
    for i, line in enumerate(lines):
        if (
            line.strip()
            and line.strip().endswith(":")
            and not line.strip().startswith(" ")
        ):
            break
        if line.strip() and _is_numpy_section_header(lines, i):
            break
        main_description.append(line)

    return "\n".join(main_description).strip()
