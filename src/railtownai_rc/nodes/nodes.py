from __future__ import annotations
import inspect
import uuid
import warnings

from abc import ABC, abstractmethod
from functools import wraps

from typing import (
    TypeVar,
    Generic,
    Type,
    List,
    Dict,
    Callable,
    ParamSpec,
)


from ..context import (
    BaseContext,
    EmptyContext,
)

_TOutput = TypeVar("_TOutput")
_TContext = TypeVar("_TContext", bound=BaseContext)


# TODO think through if there is a better way to type this.
class NodeOutput(Generic[_TOutput]):
    # TODO: write docs
    @property
    def node_type(self) -> Type[Node]:
        return self._node_type

    @property
    def data(self) -> _TOutput:
        return self._data

    def __init__(
        self,
        node_type: Type[Node],
        data: _TOutput,
    ):
        self._node_type = node_type
        self._data = data


def check_flag(flag: bool, failure_message: str):
    def wrapper_decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if flag:
                return func(*args, **kwargs)
            else:
                warnings.warn(failure_message)

        return wrapper

    return wrapper_decorator


_TNode = TypeVar("_TNode", bound="Node")
_P = ParamSpec("_P")


# this has to be class otherwise the typing can break. If you can figure our some simpler structure which allows for
# this to be types be my guest to replace to it.
class NodeFactory(Generic[_TNode]):
    def __init__(self, new_node: Callable[_P, _TNode], *args: _P.args, **kwargs: _P.kwargs):
        self.new_node = new_node
        self.args = args
        self.kwargs = kwargs

    def create(
        self,
        context: BaseContext,
        invoke_node: Callable[[Node, List[Node]], List[NodeOutput]],
        data_streamer: Callable[[str], None],
    ):
        new_node = self.new_node(*self.args, **self.kwargs)
        new_node.fill_details(context, invoke_node, data_streamer)
        return new_node


# TODO add generic for required context object
class Node(ABC, Generic[_TOutput]):
    """An abstract base class which defines some of the more basic parameters of the nodes"""

    @classmethod
    def __default_invoke_node(cls, parent_node: Node, new_nodes: List[Node]) -> List[NodeOutput]:
        # TODO write a better warning message here
        warnings.warn("You are using the default invoke node. It will not parralelize things")

        return [NodeOutput(type(n), n.invoke()) for n in new_nodes]

    @classmethod
    def __default_data_streamer(cls, data: str) -> None:
        warnings.warn("You are using the default data streamer. It will do nothing.")
        pass

    @classmethod
    def __default_context(cls) -> BaseContext:
        warnings.warn("You are using the default context. It will be empty.")
        return EmptyContext()

    def __init__(
        self,
    ):
        # TODO add type checking here.
        # if no streamer is provided it will default to the null function. n
        self.data_streamer = self.__default_data_streamer
        self.context = self.__default_context()
        self._invoke_node = self.__default_invoke_node
        self.is_filled = False
        self.uuid = str(uuid.uuid4())

    def fill_details(
        self,
        context: _TContext,
        invoke_node: Callable[[Node, List[Node]], List[NodeOutput]],
        data_streamer: Callable[[str], None],
    ):
        self.context = context
        self.data_streamer = data_streamer
        self._invoke_node = invoke_node
        self.is_filled = True

    def call_node(self, new_node: Callable[_P, Node], *args: _P.args, **kwargs: _P.kwargs) -> NodeOutput:
        """
        A special helper method for when a single node is called. It is a convenience method

        Args:
            new_node: The type of the node you would like to create.
            *args:
            **kwargs:

        Returns:

        """
        return self._invoke_node(self, [new_node(*args, **kwargs)])[0]

    # TODO: figure out a better way to type this.
    def call_nodes(self, nodes: List[NodeFactory]):
        ## TODO: extremely important documentation here.
        return self._invoke_node(
            self,
            [node_type.create(self.context, self._invoke_node, self.data_streamer) for node_type in nodes],
        )

    @classmethod
    @abstractmethod
    def pretty_name(cls) -> str: ...

    @abstractmethod
    def invoke(self) -> _TOutput:
        pass

    def state_details(self) -> Dict[str, str]:
        """
        Places the __dict__ of the current object into a dictionary of strings.
        """
        di = {k: str(v) for k, v in self.__dict__.items()}
        return di

    # TODO come up with a better method to handle this issue.
    def __getstate__(self):
        state = self.__dict__.copy()
        del state["data_streamer"]
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.data_streamer = self.__default_data_streamer
        self.is_filled = False
