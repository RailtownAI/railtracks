import uuid

import pytest
from dataclasses import dataclass

from requestcompletion.run.tools.profiling import Stamp
from requestcompletion.run.state.forest import Forest, AbstractLinkedObject


@dataclass(frozen=True)
class MockLinkedObject(AbstractLinkedObject):
    message: str


def test_simple_operations():
    heap = Forest[MockLinkedObject]()
    message_object = MockLinkedObject(
        identifier=str(uuid.uuid4()),
        message="Hello world",
        stamp=Stamp(901, 0, "Init"),
        parent=None,
    )
    heap._update_heap(message_object)
