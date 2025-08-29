import os
import re

SNIPPET_PATTERN = re.compile(r'--8<--\s*"([^"]+)"')
BLOCK_PATTERN = re.compile(r"--8<--\s*\n([\s\S]+?)\n--8<--")
START_MARKER = re.compile(r"# --8<-- \[start:(.+?)\]")
END_MARKER = re.compile(r"# --8<-- \[end:(.+?)\]")


def parse_line_selection(file_path: str, line_spec: str, workspace_root: str) -> str:
    """
    Extracts specific lines from a file based on line_spec, supporting start:end (colon) syntax,
    as well as multiple ranges separated by commas. Removes snippet markers and comments from the output.
    """
    abs_path = os.path.join(workspace_root, file_path)
    if not os.path.isfile(abs_path):
        return ""

    with open(abs_path, "r", encoding="utf-8") as src:
        code_lines = src.readlines()

    total_lines = len(code_lines)
    selected_lines = []

    for spec in line_spec.split(","):
        spec = spec.strip()
        if ":" in spec:
            start, end = (
                spec.split(":") if spec.count(":") == 1 else spec.split(":")[:2]
            )
            start = int(start) if start else 1
            end = int(end) if end else total_lines
            if start < 0:
                start += total_lines + 1
            if end < 0:
                end += total_lines + 1
            selected_lines.extend(code_lines[start - 1 : end])
        else:
            line = int(spec)
            if line < 0:
                line += total_lines + 1
            selected_lines.append(code_lines[line - 1])

    # Remove snippet markers
    cleaned_lines = [
        line
        for line in selected_lines
        if not (
            START_MARKER.match(line.strip())
            or END_MARKER.match(line.strip())
            or line.strip().startswith("# --8<--")
        )
    ]
    return "".join(cleaned_lines)


def parse_named_section(file_path: str, section_name: str, workspace_root: str) -> str:
    """
    Extracts a named snippet block from a file, identified by snippet markers.
    Returns the code between the start and end markers for the given section name.
    """
    abs_path = os.path.join(workspace_root, file_path)

    if not os.path.isfile(abs_path):
        return ""

    with open(abs_path, "r", encoding="utf-8") as src:
        code_lines = src.readlines()

    in_block = False
    block_lines = []
    found_start = False
    for line in code_lines:
        start_match = START_MARKER.match(line.strip())
        end_match = END_MARKER.match(line.strip())
        if start_match and start_match.group(1).strip() == section_name.strip():
            in_block = True
            found_start = True
            continue
        if end_match and end_match.group(1).strip() == section_name.strip():
            break
        if in_block:
            block_lines.append(line)
    if not found_start or not block_lines:
        return ""

    # Remove snippet markers
    cleaned_lines = [
        line
        for line in block_lines
        if not (
            START_MARKER.match(line.strip())
            or END_MARKER.match(line.strip())
            or line.strip().startswith("# --8<--")
        )
    ]
    return "".join(cleaned_lines)


def replace_snippet(match: re.Match, workspace_root: str) -> str:
    """
    Resolves a snippet pattern match to the corresponding code, handling line ranges, named sections, or full file extraction.
    Returns an empty string for invalid or unresolvable patterns.
    """
    snippet = match.group(1)
    if not snippet or not isinstance(snippet, str):
        return ""

    if ":" in snippet:
        file_path, after_colon = snippet.split(":", 1)
        # If after_colon is all digits, colons, commas, or negative signs, treat as line spec
        if re.match(r"^[-\d:,]+$", after_colon):
            return parse_line_selection(file_path, after_colon, workspace_root)
        else:
            return parse_named_section(file_path, after_colon, workspace_root)
    else:
        file_path = snippet
        abs_path = os.path.join(workspace_root, file_path)
        if not os.path.isfile(abs_path):
            return ""
        with open(abs_path, "r", encoding="utf-8") as src:
            code_lines = src.readlines()
        cleaned_lines = [
            line
            for line in code_lines
            if not (START_MARKER.match(line.strip()) or END_MARKER.match(line.strip()))
        ]
        return "".join(cleaned_lines)


def replace_block(match: re.Match, workspace_root: str) -> str:
    """
    Resolves a block pattern match to the concatenated code from all referenced files/snippets in the block.
    Skips files prefixed with ';'. Returns empty string for invalid patterns.
    extracted_content = []
    """
    files = match.group(1).strip().splitlines()
    extracted_content = []

    for file in files:
        file = file.strip()
        if file.startswith(";"):  # Skip files prefixed with `;`
            continue
        match = SNIPPET_PATTERN.match(f'--8<-- "{file}"')
        if match is not None:
            extracted_content.append(replace_snippet(match, workspace_root))
        else:
            # Optionally, append an empty string or log a warning
            extracted_content.append("")
    return "".join(extracted_content)


def extract_snippets(content: str, workspace_root: str) -> str:
    """
    Extracts and replaces all snippet and block patterns in the given content using the workspace root.
    Returns the content with all snippet references replaced by their corresponding code.
    """

    def snippet_replacer(match) -> str:
        return replace_snippet(match, workspace_root)

    def block_replacer(match) -> str:
        return replace_block(match, workspace_root)

    content = SNIPPET_PATTERN.sub(snippet_replacer, content)
    content = BLOCK_PATTERN.sub(block_replacer, content)
    return content
