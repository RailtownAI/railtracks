---
type: regex
pattern: '\bstrategy\s*='
match: not_contains
target: {source: file, path: main.py}
---
PyPDFLoader's option is breakdown_strategy, not strategy.
