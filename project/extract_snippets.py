import os
import re
import sys

SNIPPET_PATTERN = re.compile(r'--8<--\s*"([^"]+)"')
START_MARKER = re.compile(r"# --8<-- \[start:.*\]")
END_MARKER = re.compile(r"# --8<-- \[end:.*\]")
HEADER_COMMENT = re.compile(r"# Snippet from .+")

# Extracts code snippets referenced in markdown via PyModwn syntax, and cleans them for embedding
# Removes header comments and snippet markers from output


def extract_snippets(md_path, workspace_root, output_path):
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
    snippets = SNIPPET_PATTERN.findall(md_content)
    output_lines = []
    for snippet in snippets:
        # snippet format: path[:label]
        if ":" in snippet:
            file_path, _ = snippet.split(":", 1)
        else:
            file_path = snippet
        abs_path = os.path.join(workspace_root, file_path)
        if not os.path.isfile(abs_path):
            output_lines.append(f"# [ERROR] File not found: {abs_path}\n")
            continue
        with open(abs_path, "r", encoding="utf-8") as src:
            code_lines = src.readlines()
        # Remove header comments and snippet markers
        for line in code_lines:
            if HEADER_COMMENT.match(line):
                continue
            if START_MARKER.match(line.strip()):
                continue
            if END_MARKER.match(line.strip()):
                continue
            output_lines.append(line)
        output_lines.append("\n")
    with open(output_path, "w", encoding="utf-8") as out:
        out.writelines(output_lines)
    print(f"Extracted {len(snippets)} cleaned snippets to {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python extract_snippets.py <markdown_file> <output_file>")
        sys.exit(1)
    md_path = sys.argv[1]
    output_path = sys.argv[2]
    workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    extract_snippets(md_path, workspace_root, output_path)
