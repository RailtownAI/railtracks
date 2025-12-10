from typing import overload, Callable, Literal, TypeVar, ParamSpec

from ...nodes.utils import Node
from ..evaluators import Evaluator

from ..data import Dataset, DataPoint
from ... import AgentDataPoint

from railtracks.built_nodes.concrete import RTFunction
from railtracks.nodes.nodes import Node

_P = ParamSpec("_P")
_TOutput = TypeVar("_TOutput")

@overload
def evaluate(
        evaluator: list[Evaluator],
        data:  AgentDataPoint | list[AgentDataPoint] | Dataset,
        agent: None = None,
        mode : Literal["online", "offline"] = "offline",
):
    ...

@overload
def evaluate(
        evaluator: list[Evaluator],
        data:  DataPoint | list[DataPoint] | Dataset,
        agent: Callable[_P, Node[_TOutput]] | RTFunction[_P, _TOutput],
        mode : Literal["online", "offline"] = "online",
):
    ...

def evaluate(
        evaluator: list[Evaluator],
        data:  DataPoint | list[DataPoint] | Dataset | AgentDataPoint | list[AgentDataPoint],
        agent: Callable[_P, Node[_TOutput]] | RTFunction[_P, _TOutput] | None = None,
        mode : Literal["online", "offline"] = "offline",
):
    pass
    
