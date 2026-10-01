---
type: regex
pattern: 'agent_node\([^)]*\bllm\s*='
flags: s
target: {source: file, path: main.py}
---
Every agent_node call passes llm=.
