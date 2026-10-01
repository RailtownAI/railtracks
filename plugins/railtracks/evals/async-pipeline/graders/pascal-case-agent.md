---
type: regex
pattern: '^\s*[a-z_][a-z0-9_]*\s*=\s*rt\.agent_node\('
flags: m
match: not_contains
target: {source: file, path: main.py}
---
Agent variables are PascalCase.
