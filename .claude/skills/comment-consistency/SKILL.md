---
name: comment-consistency
description: >
  Apply railtracks' code/comment/docstring consistency rules whenever writing or editing Python code in
  this repo — new functions, modified signatures, docstrings, comments, or error messages. Use this
  automatically as part of any code change, not just when explicitly asked to clean up comments.
---

# Comment & code consistency

Before finishing any code change in this repo, check the diff against these rules. Each one comes from a
recurring, repeated PR review comment on railtracks, not a hypothetical style preference.

- **Imports**: top-level only. No local/inline imports inside functions.
- **Docstrings**: must match the actual signature, param names, types, `| None` / `Iterable[...]` etc.
  Update the docstring any time a signature changes.
- **Module-level comment strings**: a docstring at the top of a file is welcome. Avoid long inline
  paragraph-style comments in the body of the code — keep inline comments short and targeted.
- **Typing**: no bare `Any` when a concrete type is available or already imported nearby.
- **TODOs**: no inline `# TODO` comments. Either fix it now or file a tracked GitHub issue and reference it.
- **Cruft**: no dead/commented-out code, no stray debug/scratch files left in a change.
- **Mutable defaults**: don't store a mutable default (`x or []`) by reference and mutate it later — copy
  defensively.
- **Errors**: use `repr(e)` rather than `str(e)` in error/log messages.
- **`__init__.py`**: don't add docstrings to `__init__.py` files — not this repo's convention.
- **Consistency with siblings**: when adding a new variant of something that already has 2+ siblings
  (chunkers, loaders, LLM providers, etc.), match their existing shape/behavior rather than introducing an
  ad hoc one-off.
