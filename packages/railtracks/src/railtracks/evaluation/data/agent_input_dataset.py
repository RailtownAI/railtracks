from typing import Any, TypeVar, Generic, ParamSpec

_P = ParamSpec("_P")

_Args_Kwargs = TypeVar("_Args_Kwargs", bound=tuple[tuple, dict])

class AgentInputDataset(Generic[_P]):
    def __init__(
        self,
        input: list[_Args_Kwargs],
    ):
        self.input = input