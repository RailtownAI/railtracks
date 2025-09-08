import time
from typing import Dict, List, Literal, get_args

from railtracks.pubsub.messages import (
    ExecutionConfigurations,
    RequestCompletionMessage,
    RequestCreationFailure,
    RequestFinishedBase,
    RequestSuccess,
)
from railtracks.pubsub.publisher import RTPublisher

from .execution_strategy import TaskExecutionStrategy
from .task import Task


class Job:
    def __init__(
        self,
        request_id: str,
        parent_node_id: str,
        child_node_id: str,
        status: Literal["opened", "closed"],
        result: Literal["success", "failure"] | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
    ):
        """
        A simple object that represents a job to be completed.

        Args:
            request_id (str): The unique identifier for the request.
            parent_node_id (str): The ID of the parent node in the workflow.
            child_node_id (str): The ID of the child node in the workflow.
            status (Literal["opened", "closed"]): The status of the job.
            result (Literal["success", "failure"] | None): The result of the job, if completed.
            start_time (float): The time when the job started.
            end_time (float): The time when the job ended.
        """
        self.request_id = request_id
        self.parent_node_id = parent_node_id
        self.child_node_id = child_node_id
        self.status = status
        self.result = result
        self.start_time = start_time
        self.end_time = end_time

    @classmethod
    def create_new(
        cls,
        task: Task,
    ):
        """Creates a new job from a given task.

        Note it will timestamp the start time to `time.time()` and set it to 'opened' status.
        """
        return cls(
            request_id=task.request_id,
            parent_node_id=task.node.uuid,
            child_node_id=task.node.uuid,
            status="opened",
            start_time=time.time(),
        )

    def end_job(self, result: Literal["success", "failure"]):
        """
        Ends the job with the given result.

        Note this will set the end time to `time.time()` and change the status to 'closed'.

        Args:
            result (Literal["success", "failure"]): The result of the job.
        """
        self.result = result
        self.status = "closed"
        self.end_time = time.time()

    def __str__(self):
        return f"Job(request_id={self.request_id}, status={self.status}, result={self.result}, start_time={self.start_time}, end_time={self.end_time})"


class CoordinatorState:
    """
    A simple object that stores the state of the coordinator in terms of the jobs it has and is currently processing.

    The API supports simple operations that will allow you to interact with the jobs.
    """

    def __init__(self, job_list: List[Job] | None = None):
        if job_list is None:
            job_list = []

        self.job_list: List[Job] = job_list

    @classmethod
    def empty(cls):
        """
        Creates an empty CoordinatorState instance.

        One which no jobs have been completed
        """
        return cls()

    def add_job(self, task: Task):
        """
        Adds a job to the coordinator state.

        Args:
            task (Task): The task to create a job from.

        """
        new_job = Job.create_new(task)
        self.job_list.append(new_job)

    def end_job(self, request_id: str, result: Literal["success", "failure"]):
        """
        End a job with the given request_id and result.
        """
        for job in self.job_list:
            if job.request_id == request_id and job.status == "opened":
                job.end_job(result)
                return

        raise ValueError(f"No open job found with request_id: {request_id}")

    def __str__(self):
        return ",".join([str(x) for x in self.job_list])


# Note the coordinator will be the concrete invoker of the commands
class Coordinator:
    """
    The coordinator object is the concrete invoker of tasks that are passed into any of the configured execution strategies.
    """

    # we have a fairly hard dependency on the execution modes. This is a bit of a dependency hack for catching errors early.
    def __init__(
        self,
        execution_modes: Dict[ExecutionConfigurations, TaskExecutionStrategy]
        | None = None,
    ):
        self.state = CoordinatorState.empty()
        assert set(execution_modes.keys()) == set(get_args(ExecutionConfigurations)), (
            "You must provide all execution modes."
        )
        self.execution_strategy = execution_modes

    def start(self, publisher: RTPublisher):
        """
        Starts the coordinator by attaching any relevant subscribers to the provided publisher.
        """
        publisher.subscribe(self.handle_item, name="Coordinator Subscriber")

    def handle_item(self, item: RequestCompletionMessage):
        """
        The basic handler to attach to the RequestCompletionPublisher.
        """
        if isinstance(item, RequestFinishedBase):
            # we ignore requests that were never created.
            if isinstance(item, RequestCreationFailure):
                return
            self.state.end_job(
                item.request_id,
                "success" if isinstance(item, RequestSuccess) else "failure",
            )

    async def submit(
        self,
        task: Task,
        mode: ExecutionConfigurations,
    ):
        """
        Submits a task to the coordinator for execution.

        Args:
            task (Task): The task to be executed.
            mode (ExecutionConfigurations): The execution mode to use for the task.
        """
        self.state.add_job(task)

        return await self.execution_strategy[mode].execute(task)

    def system_detail(self) -> CoordinatorState:
        """
        Collects and returns details about the current state of Coordinator
        """
        return self.state

    def shutdown(self):
        """
        Shuts down all active execution strategies.
        """
        for strategy in self.execution_strategy.values():
            strategy.shutdown()
