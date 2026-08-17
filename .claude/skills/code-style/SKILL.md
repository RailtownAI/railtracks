---
name: code-style
description: >
  Apply railtracks' code-style conventions whenever writing or editing Python code in this repo —
  new functions, modified signatures, docstrings, comments, imports, error handling. Use this
  automatically as part of any code change, not just when explicitly asked to clean up code.
---

# Code style

Before finishing any code change in this repo, check the diff against these rules. Each one comes from a
recurring, repeated PR review comment on railtracks — not a hypothetical style preference.

- **Lint/format**: run `ruff check --fix` and `ruff format` — required for every PR (CI-enforced), so treat
  a change as unfinished until both are clean.
- **Imports**: prefer top-level imports. Local/inline imports are fine when there's a real reason (e.g.
  deferring an expensive or optional dependency like `litellm`) — don't add them out of habit, and don't
  let a lint failure be the excuse either way.
- **Tests**: new functionality gets tests in the matching package's `tests/` directory; don't leave a
  behavior change uncovered.
- **Docstrings**: must match the actual signature — param names, types, `| None` / `Iterable[...]` etc.
  Update the docstring any time a signature changes.
- **Module-level comment strings**: a docstring at the top of a file is welcome. Avoid long inline
  paragraph-style comments in the body of the code — keep inline comments short and targeted.
- **Typing**: no bare `Any` when a concrete type is available or already imported nearby. Don't reach for
  `Any` as a quick fix to silence something that's actually broken, either — fix the real type mismatch.
- **TODOs**: no inline `# TODO` comments. Either fix it now or file a tracked GitHub issue and reference it.
- **Cruft**: no dead/commented-out code, no stray debug/scratch files left in a change.
- **Mutable defaults**: don't store a mutable default (`x or []`) by reference and mutate it later — copy
  defensively.
- **Errors**: use `repr(e)` rather than `str(e)` in error/log messages.
- **`__init__.py`**: don't add docstrings to `__init__.py` files — not this repo's convention.
- **Consistency with siblings**: when adding a new variant of something that already has 2+ siblings
  (chunkers, loaders, LLM providers, etc.), match their existing shape/behavior rather than introducing an
  ad hoc one-off.
