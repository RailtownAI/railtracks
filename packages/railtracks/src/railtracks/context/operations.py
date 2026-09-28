from __future__ import annotations

from typing import Any, KeysView

from railtracks.events.context import (
    record_delete,
    record_get,
    record_put,
    record_update,
)

from .central import safe_get_runner_context


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
