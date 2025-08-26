import os
import re
import sys

SNIPPET_PATTERN = re.compile(r'--8<--\s*"([^"]+)"')
BLOCK_PATTERN = re.compile(r"--8<--\s*\n([\s\S]+?)\n--8<--")
START_MARKER = re.compile(r"# --8<-- \[start:(.+?)\]")
END_MARKER = re.compile(r"# --8<-- \[end:(.+?)\]")


def parse_line_selection(file_path, line_spec):
    abs_path = os.path.join(workspace_root, file_path)
    if not os.path.isfile(abs_path):
        return f"# [ERROR] File not found: {abs_path}\n"
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
            selected_lines.extend(code_lines[: int(spec)])
    return "".join(selected_lines)


def parse_named_section(file_path, section_name):
    abs_path = os.path.join(workspace_root, file_path)
    if not os.path.isfile(abs_path):
        return f"# [ERROR] File not found: {abs_path}\n"
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
        return f"# [ERROR] Snippet block '{section_name}' not found or empty in {file_path}\n"
    return "".join(block_lines)


def replace_snippet(match):
    snippet = match.group(1)
    if ":" in snippet:
        file_path, after_colon = snippet.split(":", 1)
        # If after_colon is all digits, colons, commas, or negative signs, treat as line spec
        if re.match(r"^[-\d:,]+$", after_colon):
            return parse_line_selection(file_path, after_colon)
        else:
            return parse_named_section(file_path, after_colon)
    else:
        file_path = snippet
        abs_path = os.path.join(workspace_root, file_path)
        if not os.path.isfile(abs_path):
            return f"# [ERROR] File not found: {abs_path}\n"
        with open(abs_path, "r", encoding="utf-8") as src:
            code_lines = src.readlines()
        cleaned_lines = [
            line
            for line in code_lines
            if not (START_MARKER.match(line.strip()) or END_MARKER.match(line.strip()))
        ]
        return "".join(cleaned_lines)


def replace_block(match):
    files = match.group(1).strip().splitlines()
    extracted_content = []
    for file in files:
        file = file.strip()
        if file.startswith(";"):  # Skip files prefixed with `;`
            continue
        extracted_content.append(
            replace_snippet(SNIPPET_PATTERN.match(f'--8<-- "{file}"'))
        )
    return "".join(extracted_content)


def extract_snippets(content, workspace_root):
    content = SNIPPET_PATTERN.sub(replace_snippet, content)
    content = BLOCK_PATTERN.sub(replace_block, content)
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
