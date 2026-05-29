from typing import Any, Callable, Coroutine, Generic, ParamSpec, Protocol, TypeVar

_P = ParamSpec("_P")
_T = TypeVar("_T")


class Wrapper(Protocol, Generic[_P, _T]):
    def __call__(
        self, function: Callable[_P, Coroutine[Any, Any, _T]]
    ) -> Callable[_P, Coroutine[Any, Any, _T]]: ...
