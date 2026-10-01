---
type: regex
pattern: 'guardrails\s*='
match: not_contains
target: {source: file, path: main.py}
---
The removed guardrails= argument isn't used.
