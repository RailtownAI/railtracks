from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple


class RCAction(ABC):
    @abstractmethod
    def to_logging_msg(self) -> str:
        """Creates a string representation of this action designed to be logged"""
        pass


class RequestCreationAction(RCAction):
    def __init__(
        self,
        parent_node_name: str,
        child_node_name: str,
        input_args: Tuple[Any, ...],
        input_kwargs: Dict[str, Any],
    ):
        self.parent_node_name = parent_node_name
        self.child_node_name = child_node_name
        self.args = input_args
        self.kwargs = input_kwargs

    def to_logging_msg(self) -> str:
        return f"{self.parent_node_name} CREATED {self.child_node_name}"


class RequestSuccessAction(RCAction):
    def __init__(
        self,
        child_node_name: str,
        output: Any,
    ):
        self.child_node_name = child_node_name
        self.output = output

    def to_logging_msg(self) -> str:
        return f"{self.child_node_name} DONE"


class RequestFailureAction(RCAction):
    def __init__(
        self,
        node_name: str,
        exception: Exception,
    ):
        self.node_name = node_name
        self.exception = exception

    def to_logging_msg(self) -> str:
        return f"{self.node_name} FAILED"


def arg_kwarg_logging_str(args, kwargs):
    """A helper function which converts the input args and kwargs into a string for pretty logging."""
    args_str = ", ".join([str(a) for a in args])
    kwargs_str = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
    return f"({args_str}, {kwargs_str})"
