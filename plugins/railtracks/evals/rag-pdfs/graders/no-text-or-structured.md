---
type: regex
pattern: '\.(text|structured)\b'
match: not_contains
target: {source: file, path: main.py}
---
Results aren't read with .text or .structured.
