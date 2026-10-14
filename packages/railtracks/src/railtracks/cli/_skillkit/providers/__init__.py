"""One `InstallTarget` per supported assistant.

Each provider file owns everything specific to its assistant — the root path, the
frontmatter projection, and any quirks (Cursor's `globs` → `paths` alias,
Claude's argument-hint substitution). Adding another assistant is a copy of one
of these files plus a re-export line below; `install.py` does not change.
"""

from .claude import CLAUDE
from .codex import CODEX
from .copilot import COPILOT
from .cursor import CURSOR

__all__ = ["CLAUDE", "CODEX", "COPILOT", "CURSOR"]
