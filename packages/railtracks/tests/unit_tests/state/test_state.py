import pytest
from unittest.mock import MagicMock, AsyncMock
import asyncio
from railtracks.state.state import RTState
from railtracks.utils.profiling import Stamp
from railtracks.state.request import Failure

# ================== START RTState: Construction and Properties ==================
def test_rcstate_init_and_is_empty(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher):
    state = RTState(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher)
    # is_empty: should reflect the heaps
    assert state.is_empty is True
    # Add something to one of the heaps
    state._node_heap._heap["x"] = MagicMock()
    assert state.is_empty is False
    # Logger set
    assert hasattr(state, "logger")

def test_rcstate_add_stamp(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher):
    state = RTState(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher)
    state.add_stamp("mymsg")
    # Should call stamper.create_stamp
    assert state._stamper.stamps == ["mymsg"]

def test_rcstate_shutdown_invokes_coordinator(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher):
    state = RTState(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher)
    state.shutdown()
    mock_coordinator.shutdown.assert_called_once()
# ================= END RTState: Construction and Properties ====================


# ================= START RTState: Node and Request Creation =====================
def test_create_node_and_request(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher):
    state = RTState(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher)
    node_type = MagicMock()
    node_type.pretty_name.return_value = "TestNode"
    node_type.return_value = node_type  # self "constructs" to itself

    state._node_heap.get_node_type = lambda x: MagicMock(pretty_name=lambda: "ParentNode")
    state._node_heap.update = MagicMock()
    state._request_heap.create = MagicMock(side_effect=lambda *args, **kwargs: "reqid")
    state._create_new_request_set = MagicMock(return_value=["reqid"])
    result = state._create_node_and_request(
        parent_node_id="parent",
        request_id="reqid",
        node=node_type,
        args=(1, 2),
        kwargs={"foo": "bar"},
    )
    assert result == "reqid"
    state._node_heap.update.assert_called()
# ================= END RTState: Node and Request Creation ======================

# ================= START RTState: Cancel/Info =====================
@pytest.mark.asyncio
async def test_cancel_updates_request(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher, req_forest, node_forest, req_template_factory):
    # Setup state with one node and one request
    dummy_execution_info.node_forest = node_forest
    dummy_execution_info.request_forest = req_forest
    req = req_template_factory(identifier="rid", sink_id="sid")
    node_forest._heap["sid"] = MagicMock()
    req_forest._heap["rid"] = req

    state = RTState(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher)
    state._stamper.create_stamp = MagicMock(return_value=Stamp(1,1,"t"))
    state._request_heap.update = MagicMock()
    state._request_heap.get_request_from_child_id = lambda nid: "rid"
    # Should not assert as node_id is present
    await state.cancel("sid")
    state._request_heap.update.assert_called()

@pytest.mark.asyncio
async def test_cancel_asserts_if_node_id_is_missing(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher, node_forest):
    # Should assert if node_id is missing
    state = RTState(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher)
    state._node_heap = node_forest
    with pytest.raises(AssertionError):
        await state.cancel("DOESNOTEXIST")

def test_info_and_get_info_filters_and_returns(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher, monkeypatch):
    state = RTState(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher)
    # .info returns execution info referencing live data
    assert state.info.node_forest is dummy_execution_info.node_forest
    # .get_info invokes create_sub_state_info
    dummy_execution_info.node_forest._heap["x"] = MagicMock()
    dummy_execution_info.request_forest._heap["req"] = MagicMock()
    monkeypatch.setattr(
        "railtracks.state.state.create_sub_state_info",
        lambda n, r, ids: (MagicMock(), MagicMock()),
    )
    r = state.get_info(["x"])
    assert hasattr(r, "node_forest") and hasattr(r, "request_forest")
# ============= END RTState: Cancel/Info =====================

# ================== START RTState: Exception Handling/Run ======================
@pytest.mark.asyncio
async def test__handle_failed_request_fatal_and_config(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher):
    state = RTState(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher)
    # End on error config
    dummy_executor_config.end_on_error = True
    exc = Exception("fail")
    state.logger = MagicMock()
    state.publisher.publish = AsyncMock()
    output = await state._handle_failed_request("name", "rid", exc)
    assert isinstance(output, type(Failure(exc)))
    
    # NodeInvocationError.fatal
    class FatalNodeExc(Exception): fatal = True
    output = await state._handle_failed_request("name", "rid", FatalNodeExc())
    assert isinstance(output, type(Failure(exc)))

@pytest.mark.asyncio
async def test__handle_failed_request_default(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher):
    state = RTState(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher)
    dummy_executor_config.end_on_error = False
    exc = Exception("fail")
    state.logger = MagicMock()
    state.publisher.publish = AsyncMock()
    res = await state._handle_failed_request("name", "rid", exc)
    assert isinstance(res, type(Failure(exc)))
# ============ END RTState: Exception Handling/Run =============

# ================= START RTState publisher subscribe test =============
def test_publisher_subscribe_called_on_init(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher):
    RTState(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher)
    # Ensure the subscription is set up on init (any_handler used for dummy check)
    args, kwargs = mock_publisher.subscribe.call_args
    assert args[1] == "State Object Handler"
    assert callable(args[0])
# ================ END RTState publisher subscribe test ================

# ================= START RTState create_new_request_set tests ==============
def test_create_new_request_set_asserts_on_missing_node(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher):
    state = RTState(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher)
    # patch _node_heap so one id is missing
    state._node_heap.__contains__ = lambda self, k: False
    with pytest.raises(AssertionError):
        state._create_new_request_set(
            parent_node='parent',
            children=['not_in_heap'],
            input_args=[()],
            input_kwargs=[{}],
            stamp=MagicMock(),
        )
# =============== END RTState create_new_request_set tests ================

# ================= START RTState add_stamp usage tests ==============
def test_add_stamp_multiple(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher):
    state = RTState(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher)
    msgs = ["foo", "bar", "baz"]
    for msg in msgs:
        state.add_stamp(msg)
    assert dummy_execution_info.stamper.stamps == msgs
# =============== END RTState add_stamp usage tests =================

# =========== START RTState handle_result unknown type tests ==========
def test_handle_unknown_message_type(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher):
    state = RTState(dummy_execution_info, dummy_executor_config, mock_coordinator, mock_publisher)
    # Should raise for unhandled message type
    class X: pass
    msg = X()
    with pytest.raises(TypeError):
        asyncio.run(state.handle_result(msg))
# =========== END RTState handle_result unknown type tests ============

# NOTE: state.py file is a central and important file for the system. It should have **very thourough**  integration tests.