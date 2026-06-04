import asyncio
import inspect
from typing import Iterator

from railtracks.built_nodes.gateway_types import GatewayPreMapper


def _validate_pre_mappers(mappers: list) -> None:
    for i, mapper in enumerate(mappers):
        if not callable(mapper):
            raise TypeError(
                f"Pre-mapper at index {i} is not callable: {mapper!r}"
            )
        if not inspect.iscoroutinefunction(mapper):
            raise TypeError(
                f"Pre-mapper at index {i} must be an async function (coroutine function): {mapper!r}"
            )


class GatewayManager:
    """
    Manages ordered execution of gateway pre-mappers across system and user layers.

    Internal structure — three layers executed left-to-right:
        Layer 0  (_sys_pre):  system-managed; runs first
        Layer 1  (_user):     user-provided; never modified after construction
        Layer 2  (_sys_post): system-managed; runs last

    Public interface (``__iter__``, ``__len__``, ``__getitem__``) exposes **only**
    the user layer, so iteration over a ``GatewayManager`` behaves identically to
    iterating over the original list the user passed.

    System components (e.g. context injection in ``NodeBuilder.llm``) call
    ``_add_sys_pre`` / ``_add_sys_post`` to register mappers in the reserved layers
    without touching the user layer.
    """

    def __init__(self, user_mappers: list[GatewayPreMapper] | None = None) -> None:
        self._sys_pre: list[GatewayPreMapper] = []
        self._user: list[GatewayPreMapper] = list(user_mappers or [])
        self._sys_post: list[GatewayPreMapper] = []

    @classmethod
    def from_user_input(
        cls,
        mappers: "list[GatewayPreMapper] | GatewayManager | None",
    ) -> "GatewayManager":
        """
        Convert user input into a fresh ``GatewayManager``.

        Always produces a new instance — the caller's list or ``GatewayManager``
        is never mutated.  When a ``GatewayManager`` is passed, only its user layer
        is carried over; sys layers are left empty so each ``Gateway`` instance
        manages its own system mappers independently.
        """
        if mappers is None:
            return cls()
        if isinstance(mappers, GatewayManager):
            return cls(list(mappers._user))
        _validate_pre_mappers(mappers)
        return cls(list(mappers))

    # ------------------------------------------------------------------
    # Internal system API (not intended for user code)
    # ------------------------------------------------------------------

    def _add_sys_pre(self, mapper: GatewayPreMapper) -> None:
        """Append a mapper to the system prefix layer (runs before user mappers)."""
        self._sys_pre.append(mapper)

    def _add_sys_post(self, mapper: GatewayPreMapper) -> None:
        """Append a mapper to the system suffix layer (runs after user mappers)."""
        self._sys_post.append(mapper)

    def _execution_order(self) -> list[GatewayPreMapper]:
        """Flat ordered list for execution: sys_pre → user → sys_post."""
        return self._sys_pre + self._user + self._sys_post

    # ------------------------------------------------------------------
    # Public list-like interface (user layer only)
    # ------------------------------------------------------------------

    def __iter__(self) -> Iterator[GatewayPreMapper]:
        return iter(self._user)

    def __len__(self) -> int:
        return len(self._user)

    def __getitem__(self, index: int) -> GatewayPreMapper:
        return self._user[index]

    def __repr__(self) -> str:
        return (
            f"GatewayManager("
            f"user={self._user!r}, "
            f"sys_pre={self._sys_pre!r}, "
            f"sys_post={self._sys_post!r})"
        )
