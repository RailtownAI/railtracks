from __future__ import annotations

from typing import List, TypeVar


from ..nodes.nodes import Node
from ..context import (
    BaseContext,
    EmptyContext,
)

from .config import ExecutorConfig
from .tools.profiling import Stamp, StampManager
from .tools.stream import Subscriber
from .state.request import RequestForest
from .state.node import NodeForest
from .visuals.agent_viewer import AgentViewer


_TContext = TypeVar("_TContext", bound=BaseContext)
_TOutput = TypeVar("_TOutput")


# TODO add some the logic for an optional architecture requirement.
class ExecutionInfo:
    def __init__(
        self,
        request_heap: RequestForest,
        node_heap: NodeForest,
        stamper: StampManager,
        context: BaseContext = EmptyContext(),
        subscriber: Subscriber[str] | None = None,
        exception_history: List[Exception] = None,
        executor_config: ExecutorConfig = ExecutorConfig(),
    ):
        self.request_heap = request_heap
        self.node_heap = node_heap
        self.stamper = stamper
        self.context = context
        self.subscriber = subscriber
        self.exception_history = (
            exception_history if exception_history is not None else []
        )
        self.executor_config = executor_config

    @classmethod
    def create_new(
        cls,
        start_node: Node,
        context: BaseContext = EmptyContext(),
        subscriber: Subscriber[str] | None = None,
        executor_config: ExecutorConfig = ExecutorConfig(),
    ) -> ExecutionInfo:
        request_heap = RequestForest()
        node_heap = NodeForest()
        stamper = StampManager()
        first_stamp = stamper.create_stamp(
            f"Opened a new request between the start and the {start_node.pretty_name()}"
        )

        node_heap.update(start_node, first_stamp)
        request_heap.create(
            identifier="START",
            source_id=None,
            sink_id=start_node.uuid,
            stamp=first_stamp,
        )

        return ExecutionInfo(
            request_heap=request_heap,
            node_heap=node_heap,
            stamper=stamper,
            context=context,
            subscriber=subscriber,
            exception_history=[],
            executor_config=executor_config,
        )

    @property
    def answer(self) -> _TOutput:
        """Convenience method to access the answer of the run."""
        return self.request_heap.answer

    @property
    def all_stamps(self) -> List[Stamp]:
        """Convenience method to access all the stamps of the run."""
        return self.stamper.all_stamps

    def view_graph(self):
        AgentViewer(self.all_stamps, self.request_heap, self.node_heap).display_graph()

