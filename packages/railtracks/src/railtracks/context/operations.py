from __future__ import annotations

from typing import Any, KeysView, Protocol, TypeVar

from railtracks.events.context import (
    record_delete,
    record_get,
    record_put,
    record_update,
)

from .central import get_owned_state, safe_get_runner_context

_T = TypeVar("_T")


def get(
    key: str,
    /,
    default: Any | None = None,
) -> Any:
    """
    Get a value from context

    Args:
        key (str): The key to retrieve.
        default (Any | None): The default value to return if the key does not exist. If set to None and the key does not exist, a KeyError will be raised.
    Returns:
        Any: The value associated with the key, or the default value if the key does not exist.

    Raises:
        KeyError: If the key does not exist and no default value is provided.
    """
    context = safe_get_runner_context()
    value = context.external_context.get(key, default=default)
    record_get(key, value)
    return value


def put(
    key: str,
    value: Any,
) -> None:
    """
    Set a value in the context.

    Args:
        key (str): The key to set.
        value (Any): The value to set.
    """
    context = safe_get_runner_context()
    context.external_context.put(key, value)
    record_put(key, value)


def update(data: dict[str, Any]) -> None:
    """
    Sets the values in the context. If the context already has values, this will overwrite them, but it will not delete any existing keys.

    Args:
        data (dict[str, Any]): The data to update the context with.
    """
    data = dict(data)
    context = safe_get_runner_context()
    context.external_context.update(data)
    record_update(data)


def delete(key: str) -> None:
    """
    Delete a key from the context.

    Args:
        key (str): The key to delete.

    Raises:
        KeyError: If the key does not exist.
    """
    context = safe_get_runner_context()
    context.external_context.delete(key)
    record_delete(key)


def keys() -> KeysView[str]:
    """
    Get the keys of the context.

    Returns:
        KeysView[str]: The keys in the context.
    """
    context = safe_get_runner_context()
    return context.external_context.keys()


class StateOwner(Protocol):
    """Anything with a stable ``type_id``: a middleware instance or a node class."""

    @property
    def type_id(self) -> str: ...


def local(cls: type[_T], /, *, owner: StateOwner | None = None) -> _T:
    """
    Get the state the running middleware or node keeps for this session.

    Each owner gets one instance of ``cls`` per session, created by calling ``cls()`` the first time it asks. Every node and call in the session that runs the same owner sees that instance, a new session starts from a fresh one, and concurrent sessions never share it. The owner is the innermost middleware or node body that is running, so a middleware instance, a decorator-built middleware, and a tool each get their own state without choosing a key.

    The state is not part of the context dictionary: it is never recorded as a context event, never shown by ``keys()``, and ends with the session.

    Args:
        cls: The state's class, called with no arguments to create it. A dataclass with defaults keeps several fields together.
        owner: The middleware instance or node class whose state to get. Defaults to the one that is running; pass it to read an owner's state from elsewhere in the session.

    Returns:
        The owner's instance of ``cls`` for this session.

    Raises:
        ContextError: Outside a session, or when ``owner`` is omitted and no middleware or node is running.
    """
    return get_owned_state(cls, None if owner is None else owner.type_id)
