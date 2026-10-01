---
type: regex
pattern: 'stream\s*=\s*True'
match: not_contains
target: {source: file, path: main.py}
---
The removed stream=True model flag isn't used.
