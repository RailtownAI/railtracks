from typing import Any, Generic, Protocol, TypeVar

_T = TypeVar("_T")
_TOut = TypeVar("_TOut", covariant=True)


class MapInputs(Protocol[_TOut]):
    async def __call__(self, *args: Any, **kwargs: Any) -> _TOut: ...


class MapOutputs(Protocol, Generic[_T]):
    async def __call__(self, output: _T) -> _T: ...
