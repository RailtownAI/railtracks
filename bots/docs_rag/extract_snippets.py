import os
import re
import sys

SNIPPET_PATTERN = re.compile(r'--8<--\s*"([^"]+)"')
START_MARKER = re.compile(r"# --8<-- \[start:(.+?)\]")
END_MARKER = re.compile(r"# --8<-- \[end:(.+?)\]")
HEADER_COMMENT = re.compile(r"# Snippet from .+")


def extract_snippets(content, workspace_root):
    def replace_snippet(match):
        snippet = match.group(1)
        if ":" in snippet:
            file_path, snippet_name = snippet.split(":", 1)
        else:
            file_path = snippet
            snippet_name = None
        abs_path = os.path.join(workspace_root, file_path)
        if not os.path.isfile(abs_path):
            return f"# [ERROR] File not found: {abs_path}\n"
        with open(abs_path, "r", encoding="utf-8") as src:
            code_lines = src.readlines()
        if snippet_name:
            in_block = False
            block_lines = []
            found_start = False
            for line in code_lines:
                start_match = START_MARKER.match(line.strip())
                end_match = END_MARKER.match(line.strip())
                if start_match and start_match.group(1).strip() == snippet_name.strip():
                    in_block = True
                    found_start = True
                    continue
                if end_match and end_match.group(1).strip() == snippet_name.strip():
                    break
                if in_block and not HEADER_COMMENT.match(line):
                    block_lines.append(line)
            if not found_start or not block_lines:
                return f"# [ERROR] Snippet block '{snippet_name}' not found or empty in {file_path}\n"
            return "".join(block_lines)
        cleaned_lines = [
            line
            for line in code_lines
            if not (
                HEADER_COMMENT.match(line)
                or START_MARKER.match(line.strip())
                or END_MARKER.match(line.strip())
            )
        ]
        return "".join(cleaned_lines)

    return SNIPPET_PATTERN.sub(replace_snippet, content)


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
