from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from railtracks.context.central import (
    get_publisher,
    update_parent_id,
)
from railtracks.context.internal import InternalContext
from railtracks.nodes.nodes import NodeState
from railtracks.pubsub.messages import RequestFailure, RequestSuccess

if TYPE_CHECKING:
    from .task import Task


class TaskExecutionStrategy(ABC):
    def shutdown(self):
        pass

    @abstractmethod
    async def execute(self, task: Task):
        pass


class AsyncioExecutionStrategy(TaskExecutionStrategy):
    """
    An async-await style execution approach for tasks.

    """

    def shutdown(self):
        # there is no need for any shutdown approach for asyncio.
        pass

    async def execute(self, task: Task):
        """
        Executes the task using asyncio.

        Args:
            task (Task): The task to be executed.
        """
        invoke_func = task.invoke

        publisher = get_publisher()
        response = None
        try:
            result = await invoke_func()
            response = RequestSuccess(
                request_id=task.request_id,
                node_state=NodeState(task.node),
                result=result,
            )
        except Exception as e:
            response = RequestFailure(
                request_id=task.request_id, node_state=NodeState(task.node), error=e
            )
        finally:
            if response is not None:
                await publisher.publish(response)

        return response


class ConcurrentFuturesExecutor(TaskExecutionStrategy):
    def __init__(self, executor: concurrent.futures.Executor):
        raise NotImplementedError(
            "We currently do not support concurrent futures executor. See issue #140"
        )
        self.executor: concurrent.futures.Executor | None = executor

    def shutdown(self):
        if self.executor is not None:
            self.executor.shutdown(wait=True)
            self.executor = None

    def execute(self, task: Task):
        if inspect.iscoroutine(task.invoke):

            def non_async_wrapper():
                return asyncio.run(task.invoke())

            invoke_func = non_async_wrapper
        else:
            invoke_func = task.invoke

        publisher = get_publisher()

        def wrapped_invoke(global_vars: InternalContext):
            update_parent_id(task.node.uuid)
            try:
                result = invoke_func()
                response = RequestSuccess(
                    request_id=task.request_id,
                    node_state=NodeState(task.node),
                    result=result,
                )
            except Exception as e:
                response = RequestFailure(
                    request_id=task.request_id, node_state=NodeState(task.node), error=e
                )
            finally:
                publisher.publish(response)

        # f = self.executor.submit(wrapped_invoke, parent_global_variables)

        # return f


class ThreadedExecutionStrategy(ConcurrentFuturesExecutor):
    # TODO add config as required here
    def __init__(self):
        super().__init__(concurrent.futures.ThreadPoolExecutor())


class ProcessExecutionStrategy(TaskExecutionStrategy):
    def __init__(self):
        raise NotImplementedError(
            "We do not support Process Task Execution Strategy yet."
        )
