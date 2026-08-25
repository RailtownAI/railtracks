"""Helper functions defined under PEP 563 for annotation-resolution tests.

The ``from __future__ import annotations`` below is the whole point of this module:
every annotation in it is stored as a string at runtime.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel


class Point(BaseModel):
    """Simple model used to check pydantic resolution through a string annotation."""

    x: int
    y: int


def search_files(pattern: str, limit: int = 10) -> str:
    """Search files.

    Args:
        pattern: Regex to search for.
        limit: Max results.
    """
    return ""


def deferred_generics(
    mode: Literal["content", "files"],
    tags: List[str] | None = None,
    depth: Optional[int] = None,
    origin: Point | None = None,
) -> str:
    """Search with options.

    Args:
        mode: Where to search.
        tags: Tags to filter on.
        depth: How deep to go.
        origin: Where to start.
    """
    return ""


def takes_a_dict(payload: Dict[str, int]) -> str:
    """Not allowed as a node.

    Args:
        payload: A mapping.
    """
    return ""


def unresolvable(value: DefinitelyNotDefined) -> str:  # noqa: F821
    """Annotation references a name that does not exist at runtime.

    Args:
        value: Something.
    """
    return ""
