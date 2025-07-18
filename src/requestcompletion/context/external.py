from abc import ABC, abstractmethod
from typing import Any, Dict


class ExternalContext(ABC):
    @abstractmethod
    def update(self, data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get(self, key: str, *, default: Any | None = None):
        pass

    @abstractmethod
    def put(
        self,
        key: str,
        value: Any,
    ):
        pass

    def __setitem__(self, key, value):
        self.put(key, value)

    def __getitem__(self, item):
        return self.get(item, default=None)


class MutableExternalContext(ExternalContext):
    """
    A context that can be initially defined, then be interacted with using the `get` and `put` methods.
    """

    def __init__(
        self,
        input_dict: Dict[str, Any] | None = None,
    ):
        if input_dict is not None:
            self._context_var_store = input_dict
        else:
            self._context_var_store = {}

    def update(self, data: Dict[str, Any]) -> None:
        """
        Sets the values in the context. If the context already has values, this will overwrite them, but it will not
        delete any existing keys.
        """
        for key, value in data.items():
            self._context_var_store[key] = value

    def get(self, key: str, *, default: Any | None = None):
        """
        Gets the value of the provided key from the context. If the key does not exist, it will return the default
        value if provided (and not None), otherwise it will raise a KeyError.
        """
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
        self._context_var_store[key] = value
