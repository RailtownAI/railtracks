from typing import Any, Generic, Protocol, TypeVar

_T = TypeVar("_T")


class MapInputs(Protocol):
    async def __call__(self, *args, **kwargs) -> tuple[list[Any], dict[str, Any]]: ...


class MapOutputs(Protocol, Generic[_T]):
    async def __call__(self, output: _T) -> _T: ...
