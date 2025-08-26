import os
import re
import sys

SNIPPET_PATTERN = re.compile(r'--8<--\s*"([^"]+)"')
BLOCK_PATTERN = re.compile(r"--8<--\s*\n([\s\S]+?)\n--8<--")
START_MARKER = re.compile(r"# --8<-- \[start:(.+?)\]")
END_MARKER = re.compile(r"# --8<-- \[end:(.+?)\]")


def parse_line_selection(file_path, line_spec, workspace_root):
    abs_path = os.path.join(workspace_root, file_path)
    if not os.path.isfile(abs_path):
        return ""
    with open(abs_path, "r", encoding="utf-8") as src:
        code_lines = src.readlines()
    total_lines = len(code_lines)
    selected_lines = []
    for spec in line_spec.split(","):
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


def parse_named_section(file_path, section_name, workspace_root):
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


def replace_snippet(match, workspace_root):
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


def replace_block(match, workspace_root):
    files = match.group(1).strip().splitlines()
    extracted_content = []
    for file in files:
        file = file.strip()
        if file.startswith(";"):  # Skip files prefixed with `;`
            continue
        extracted_content.append(
            replace_snippet(SNIPPET_PATTERN.match(f'--8<-- "{file}"'), workspace_root)
        )
    return "".join(extracted_content)


def extract_snippets(content, workspace_root):
    def snippet_replacer(match):
        return replace_snippet(match, workspace_root)

    def block_replacer(match):
        return replace_block(match, workspace_root)

    content = SNIPPET_PATTERN.sub(snippet_replacer, content)
    content = BLOCK_PATTERN.sub(block_replacer, content)
    return content


if __name__ == "__main__":
    print("Testing snippet extraction:")
    if len(sys.argv) < 2:
        print("Usage: python extract_snippets.py <markdown_file>")
        sys.exit(1)
    md_path = sys.argv[1]
    workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    print(extract_snippets(content, workspace_root))
