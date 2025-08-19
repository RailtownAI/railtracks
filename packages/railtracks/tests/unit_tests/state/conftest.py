from uuid import uuid4
import pytest
from dataclasses import dataclass
from copy import deepcopy
from railtracks.utils.profiling import Stamp
from railtracks.state.forest import Forest, AbstractLinkedObject
from railtracks.state.node import LinkedNode, NodeForest
from railtracks.state.request import RequestTemplate, RequestForest
from unittest.mock import patch, MagicMock, AsyncMock

# ================= START fixtures for forest.py ====================
@dataclass(frozen=True)
class MockLinkedObject(AbstractLinkedObject):
    message: str


@pytest.fixture
def mock_linked_object():
    def _MockLinkedObject(identifier, message, stamp, parent):
        return MockLinkedObject(identifier, stamp, parent, message)
    return _MockLinkedObject

@pytest.fixture
def forest():
    return Forest[MockLinkedObject]()

@pytest.fixture
def unique_id():
    return lambda: str(uuid4())

@pytest.fixture
def example_structure():
    # (EXACTLY your earlier structure, so DRY reused as-is)
    identifier_1 = str(uuid4())
    identifier_2 = str(uuid4())
    identifier_3 = str(uuid4())

    linked1_1 = MockLinkedObject(
        identifier_1, Stamp(8091, 0, "Init"), parent=None, message="Hello world"
    )
    linked1_2 = MockLinkedObject(
        identifier_1, Stamp(8091, 1, "second try"), parent=linked1_1, message="Hello world..."
    )
    linked1_3 = MockLinkedObject(
        identifier_1, Stamp(8091, 5, "third try"), parent=linked1_2, message="Hello world...!"
    )

    linked2_1 = MockLinkedObject(
        identifier_2, Stamp(8091, 0, "Init"), parent=None, message="Hello world"
    )
    linked2_2 = MockLinkedObject(
        identifier_2, Stamp(8091, 1, "second try"), parent=linked2_1, message="Hello world..."
    )

    linked3_1 = MockLinkedObject(
        identifier_3, Stamp(8091, 1, "Init"), parent=None, message="Hello world"
    )
    linked3_2 = MockLinkedObject(
        identifier_3, Stamp(8091, 2, "second try"), parent=linked3_1, message="Hello world..."
    )
    linked3_3 = MockLinkedObject(
        identifier_3, Stamp(8091, 3, "third try"), parent=linked3_2, message="Hello world...!"
    )
    linked3_4 = MockLinkedObject(
        identifier_3, Stamp(8091, 4, "fourth try"), parent=linked3_3, message="Hello world...!!"
    )
    linked3_5 = MockLinkedObject(
        identifier_3, Stamp(8091, 5, "fifth try"), parent=linked3_4, message="Hello world...!!!"
    )

    heap = Forest[MockLinkedObject]()
    for l in [linked1_1, linked1_2, linked1_3, linked2_1, linked2_2, linked3_1, linked3_2, linked3_3, linked3_4, linked3_5]:
        heap._update_heap(l)

    return heap, {
        "1": [linked1_1, linked1_2, linked1_3],
        "2": [linked2_1, linked2_2],
        "3": [linked3_1, linked3_2, linked3_3, linked3_4, linked3_5],
    }

# ================ END fixtures for forest.py ====================

# =================== START fixtures for node.py ====================

@pytest.fixture
def dummy_node_factory():
    class DummyNode:
        _pretty = "dummy"  # class variable for name
        _type = "Tool"  # class variable for type

        def __init__(self, uuid=None, details=None):
            self.uuid = uuid or str(uuid4())
            # to keep constructor signature compatible
            self._details = details or {"dummyfield": 123}
            self._copied = False

        @property
        def details(self):
            return self._details

        @classmethod
        def name(cls):
            # match the abstract method; returns a str (static/class)
            return cls._pretty

        def safe_copy(self):
            cls = self.__class__
            result = cls(self.uuid, details=deepcopy(self.details))
            result._copied = True
            return result

        def __repr__(self):
            return f"DummyNode<{self.uuid}>"

        @classmethod
        def type(cls):
            return cls._type
        
    def _factory(uuid=None, details=None, pretty="dummy"):
        # Dynamically make a new subclass with desired _pretty
        node_cls = type(f"TestNode_{pretty}", (DummyNode,), {"_pretty": pretty})
        return node_cls(uuid=uuid, details=details)
    return _factory

@pytest.fixture
def linked_node_factory(dummy_node_factory):
    def _factory(identifier, stamp, parent=None, pretty='dummy', details=None):
        node = dummy_node_factory(uuid=identifier, pretty=pretty, details=details)
        return LinkedNode(identifier=identifier, _node=node, stamp=stamp, parent=parent)
    return _factory

@pytest.fixture
def node_forest():
    return NodeForest()

# ================ END fixtures for node.py =========================
# ================== START request.py fixtures/helpers ====================
@pytest.fixture
def req_stamp():
    def _make(step, ident="x"):
        return Stamp(time=100 + step, step=step, identifier=ident)
    return _make

@pytest.fixture
def req_template_factory(req_stamp):
    def _make(identifier="id", source_id=None, sink_id=None, input_args=(), input_kwargs=None, output=None, step=0, parent=None):
        identifier = identifier
        sink_id = sink_id or "sink"
        return RequestTemplate(
            identifier=identifier,
            source_id=source_id,
            sink_id=sink_id,
            input=(input_args, input_kwargs or {}),
            output=output,
            stamp=req_stamp(step, identifier),
            parent=parent,
        )
    return _make

@pytest.fixture
def req_forest():
    return RequestForest()

# ================ END request.py fixtures/helpers =======================

# ================= START fixtures for state.py ====================
# ---- Mock Publisher ----
@pytest.fixture
def mock_publisher():
    mock = MagicMock()
    mock.subscribe = MagicMock()
    # .publish is async for test
    async def _publish(*args, **kwargs): return None
    mock.publish = AsyncMock(side_effect=_publish)
    return mock

# ---- Mock Coordinator ----
@pytest.fixture
def mock_coordinator():
    mock = MagicMock()
    mock.shutdown = MagicMock()
    async def _submit(*args, **kwargs): return "submission_result"
    mock.submit = AsyncMock(side_effect=_submit)
    return mock

# ---- Mock Stamper/Stamp ----
@pytest.fixture
def dummy_stamper():
    class DummyStamper:
        class DummyStamp:
            def __init__(self, msg=""): self.msg = msg
            def __eq__(self, other): return isinstance(other, DummyStamper.DummyStamp)
        def __init__(self): self.stamps = []
        def create_stamp(self, msg): self.stamps.append(msg); return self.DummyStamp(msg)
        def stamp_creator(self): return lambda msg="": self.create_stamp(msg)
    # Use .stamp_creator() to match the interface in RTState
    return DummyStamper()

# ---- ExecutionInfo + ExecutorConfig dummy ----
@pytest.fixture
def dummy_execution_info(node_forest, req_forest, dummy_stamper):
    class DummyExecutionInfo:
        def __init__(self, node_forest, request_forest, stamper):
            self.node_forest = node_forest
            self.request_forest = request_forest
            self.stamper = stamper
    return DummyExecutionInfo(node_forest, req_forest, dummy_stamper)

@pytest.fixture
def dummy_executor_config():
    class DummyExecutorConfig:
        def __init__(self, end_on_error=False):
            self.end_on_error = end_on_error
    return DummyExecutorConfig()

# ---- Patch RT logger everywhere ----
@pytest.fixture(autouse=True)
def patch_rt_logger(monkeypatch):
    # Patch get_rt_logger to return a MagicMock logger for every RTState
    monkeypatch.setattr(
        "railtracks.state.state.get_rt_logger", lambda: MagicMock()
    )
# ================ END fixtures for state.py ====================