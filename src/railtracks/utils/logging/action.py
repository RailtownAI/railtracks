from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple


class RTAction(ABC):
    @abstractmethod
    def to_logging_msg(self) -> str:
        """Creates a string representation of this action designed to be logged"""
        pass


class RequestCreationAction(RTAction):
    def __init__(
        self,
        parent_node_name: str,
        child_node_name: str,
        input_args: Tuple[Any, ...],
        input_kwargs: Dict[str, Any],
    ):
        """
        A simple object that encapsulates a Request Creation.

        Args:
            parent_node_name (str): The name of the parent node that created this request.
            child_node_name (str): The name of the child node that is being created.
            input_args (Tuple[Any, ...]): The input arguments passed to the child node.
            input_kwargs (Dict[str, Any]): The input keyword arguments passed to the child node.
        """
        self.parent_node_name = parent_node_name
        self.child_node_name = child_node_name
        self.args = input_args
        self.kwargs = input_kwargs

    def to_logging_msg(self) -> str:
        return f"{self.parent_node_name} CREATED {self.child_node_name}"


class RequestCompletionBase(RTAction, ABC):
    def __init__(self, node_name: str):
        """
        A base class for when a request is completed.

        Args:
            node_name (str): The name of the child node that is being completed.
        """
        self.node_name = node_name


class RequestSuccessAction(RequestCompletionBase):
    def __init__(
        self,
        node_name: str,
        output: Any,
    ):
        """ "
        A simple abstraction of a message when a request is successfully completed.

        Args:
            node_name (str): The name of the child node that completed successfully.
            output (Any): The output produced by the child node.
        """
        super().__init__(node_name)
        self.output = output

    def to_logging_msg(self) -> str:
        return f"{self.node_name} DONE"


class RequestFailureAction(RequestCompletionBase):
    def __init__(
        self,
        node_name: str,
        exception: Exception,
    ):
        """
        A simple abstraction of a message when a request fails.
        \
        Args:
            node_name (str): The name of the child node that failed.
            exception (Exception): The exception that was raised during the request.
        """
        super().__init__(node_name)
        self.exception = exception

    def to_logging_msg(self) -> str:
        return f"{self.node_name} FAILED"


def arg_kwarg_logging_str(args, kwargs):
    """A helper function which converts the input args and kwargs into a string for pretty logging."""
    args_str = ", ".join([str(a) for a in args])
    kwargs_str = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
    return f"({args_str}, {kwargs_str})"
