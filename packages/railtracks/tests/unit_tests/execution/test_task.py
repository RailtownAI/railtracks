import pytest
from unittest.mock import patch

import pytest
import railtracks as rt
from railtracks.execution.task import Task


def hello_world():
    print("Hello, World!")


HelloWorldNode = rt.function_node(hello_world)


def test_task_invoke():
    hwn = HelloWorldNode()
    task = rt.execution.task.Task(
        node=hwn, request_id="test_request_id", arguments=((), {})
    )

    assert task.node == hwn
    assert task.request_id == "test_request_id"
