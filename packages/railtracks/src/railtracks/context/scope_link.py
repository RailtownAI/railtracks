from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class ScopeLink(Generic[T]):
    """Immutable linked chain; each link carries a reference to its parent."""

    value: T
    parent: ScopeLink[T] | None = None

    def pushed(self, value: T) -> "ScopeLink[T]":
        return ScopeLink(value=value, parent=self)

    def find(self, predicate: Callable[[T], bool]) -> T | None:
        link: ScopeLink[T] | None = self
        while link is not None:
            if predicate(link.value):
                return link.value
            link = link.parent
        return None

    def find_link(self, predicate: Callable[[T], bool]) -> "ScopeLink[T] | None":
        """Like `find`, but returns the matching *link* (not its value).

        The link exposes `.parent`, so callers can keep walking from
        the position of the match.
        """
        link: ScopeLink[T] | None = self
        while link is not None:
            if predicate(link.value):
                return link
            link = link.parent
        return None
