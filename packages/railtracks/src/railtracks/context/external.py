from __future__ import annotations

import inspect
import threading
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, ItemsView, KeysView, TypeVar

_MISSING: Any = object()
_T = TypeVar("_T")


class ExternalContext(ABC):
    @abstractmethod
    def update(self, data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get(self, key: str, *, default: Any | None = None) -> Any:
        pass

    @abstractmethod
    def put(
        self,
        key: str,
        value: Any,
    ):
        pass

    @abstractmethod
    def delete(self, key: str):
        pass

    @abstractmethod
    def keys(self) -> KeysView[str]:
        pass

    @abstractmethod
    def items(self) -> ItemsView[str, Any]:
        pass

    def mutate(
        self,
        key: str,
        fn: Callable[[Any], _T],
        *,
        default: Any = _MISSING,
    ) -> _T:
        """Read-modify-write a single key using ``fn``.

        Subclasses with internal synchronization should override this method to
        execute the read, transform, and write atomically.

        Args:
            key (str): The key to update.
            fn (Callable[[Any], _T]): Synchronous transform receiving the current
                value (or ``default`` when absent) and returning the new value.
            default (Any): Fallback value passed to ``fn`` when ``key`` is absent.
                If omitted and ``key`` is absent, ``KeyError`` is raised.

        Returns:
            _T: The new value stored under ``key``.

        Raises:
            KeyError: If ``key`` does not exist and no ``default`` is provided.
            TypeError: If ``fn`` is a coroutine function or returns a coroutine.
        """
        if inspect.iscoroutinefunction(fn):
            raise TypeError("mutate() callback must be synchronous.")

        try:
            current = self.get(key)
        except KeyError:
            if default is _MISSING:
                raise
            current = default

        new_value = fn(current)
        if inspect.iscoroutine(new_value):
            new_value.close()
            raise TypeError("mutate() callback must be synchronous.")

        self.put(key, new_value)
        return new_value

    def __setitem__(self, key, value):
        self.put(key, value)

    def __getitem__(self, item):
        return self.get(item, default=None)


class MutableExternalContext(ExternalContext):
    """
    A thread-safe context that can be initially defined, then interacted with using `get`, `put`, `update`, `delete`, and `mutate`.
    """

    def __init__(
        self,
        input_dict: Dict[str, Any] | None = None,
    ):
        if input_dict is not None:
            self._context_var_store = input_dict
        else:
            self._context_var_store = {}
        self._lock = threading.RLock()

    def _snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._context_var_store)

    def update(self, data: Dict[str, Any]) -> None:
        """
        Sets the values in the context. If the context already has values, this will overwrite them, but it will not
        delete any existing keys.
        """
        copied = dict(data)
        with self._lock:
            self._context_var_store.update(copied)

    def get(self, key: str, *, default: Any | None = None):
        """
        Gets the value of the provided key from the context. If the key does not exist, it will return the default
        value if provided (and not None), otherwise it will raise a KeyError.
        """
        with self._lock:
            try:
                result = self._context_var_store[key]
                return result
            except KeyError:
                if default is not None:
                    return default
                raise

    def put(
        self,
        key: str,
        value: Any,
    ):
        """
        Puts the value in the context under the provided key. If another value already exists under that key, it
        will be overwritten.
        """
        with self._lock:
            self._context_var_store[key] = value

    def delete(self, key: str):
        """
        Deletes the value in the context under the provided key. If the key does not exist, it will raise a KeyError.
        """
        with self._lock:
            try:
                del self._context_var_store[key]
            except KeyError:
                raise KeyError(f"Key '{key}' does not exist in the context.")

    def keys(self):
        """
        Returns a snapshot view of the keys in the context.

        Returns:
            KeysView[str]: The keys in the context.
        """
        return self._snapshot().keys()

    def items(self):
        """
        Returns a copy of the keys and values of the context.

        Returns:
            ItemsView[str, Any]: The key/value pairs in the context.
        """
        return self._snapshot().items()

    def mutate(
        self,
        key: str,
        fn: Callable[[Any], _T],
        *,
        default: Any = _MISSING,
    ) -> _T:
        """Atomically read-modify-write a single key under the context lock.

        Args:
            key (str): The key to update.
            fn (Callable[[Any], _T]): Synchronous transform receiving the current
                value (or ``default`` when absent) and returning the new value.
                Prefer returning a new value over mutating a shared container in
                place, and avoid acquiring external locks inside ``fn``.
            default (Any): Fallback value passed to ``fn`` when ``key`` is absent.
                If omitted and ``key`` is absent, ``KeyError`` is raised.

        Returns:
            _T: The new value stored under ``key``.

        Raises:
            KeyError: If ``key`` does not exist and no ``default`` is provided.
            TypeError: If ``fn`` is a coroutine function or returns a coroutine.
        """
        if inspect.iscoroutinefunction(fn):
            raise TypeError("mutate() callback must be synchronous.")

        with self._lock:
            if key in self._context_var_store:
                current = self._context_var_store[key]
            elif default is not _MISSING:
                current = default
            else:
                raise KeyError(f"Key '{key}' does not exist in the context.")

            new_value = fn(current)
            if inspect.iscoroutine(new_value):
                new_value.close()
                raise TypeError("mutate() callback must be synchronous.")

            self._context_var_store[key] = new_value
            return new_value

    def __getstate__(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if k != "_lock"}

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)
        self._lock = threading.RLock()
