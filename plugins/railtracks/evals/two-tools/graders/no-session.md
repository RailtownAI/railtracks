---
type: regex
pattern: 'rt\.[Ss]ession\b'
match: not_contains
target: {source: file, path: main.py}
---
Agents don't run through the unsupported rt.Session.
