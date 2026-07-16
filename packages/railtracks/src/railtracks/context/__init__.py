from typing import TYPE_CHECKING

from .central import (
    delete,
    get,
    keys,
    put,
    update,
)

if TYPE_CHECKING:
    from railtracks.interaction._astream import get_stream

__all__ = ["put", "get", "update", "delete", "keys", "get_stream"]


def __getattr__(name: str):
    # lazy import to avoid an import cycle (interaction imports from context.central)
    if name == "get_stream":
        from railtracks.interaction._astream import get_stream

        return get_stream
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(__all__))
