from railtracks.pubsub.messages import (
    RequestCompletionMessage, RequestSuccess, RequestFailure, RequestCreationFailure,
    RequestCreation, FatalFailure, Streaming, RequestFinishedBase
)

# ================= START RequestCompletionMessage base tests ============

def test_request_completion_message_log_message_repr():
    m = RequestCompletionMessage()
    assert isinstance(m.log_message(), str)
    assert repr(m) == m.log_message()

# ================ END RequestCompletionMessage base tests ===============

# ================= START RequestFinishedBase and subclasses tests ============

def test_request_finished_base_fields_and_node(dummy_node_state):
    # When constructed, node_state/instantiate yields node
    m = RequestFinishedBase(request_id="some_id", node_state=dummy_node_state)
    assert m.request_id == "some_id"
    assert m.node_state == dummy_node_state
    assert m.node == dummy_node_state.instantiate()

def test_request_finished_base_node_none():
    # Node is None if node_state is None
    m = RequestFinishedBase(request_id="X", node_state=None)
    assert m.node is None

def test_request_finished_base_repr(dummy_node_state):
    m = RequestFinishedBase(request_id="id3", node_state=dummy_node_state)
    r = repr(m)
    assert "id3" in r and "DummyNodeState" in r

def test_request_success_repr_and_log_message(dummy_node_state):
    m = RequestSuccess(request_id="r", node_state=dummy_node_state, result=42)
    # '__repr__' should contain result
    assert repr(m).endswith("result=42)")
    # log_message should use name() and the result value
    assert "DONE" in m.log_message()
    assert "MockNode" in m.log_message()
    assert "42" in m.log_message()

def test_request_failure_repr_and_log_message(dummy_node_state):
    err = Exception("fail")
    m = RequestFailure(request_id="r", node_state=dummy_node_state, error=err)
    # repr contains error string
    assert "fail" in repr(m)
    assert "FAILED" in m.log_message()
    assert "MockNode" in m.log_message()

def test_request_creation_failure_repr_and_log_message(dummy_exception):
    m = RequestCreationFailure(request_id="Z", error=dummy_exception)
    assert repr(m) == "RequestCreationFailure(request_id=Z, error=Something went wrong)"
    assert "FAILED" in m.log_message()
    assert "Something went wrong" in m.log_message()

# ================ END RequestFinishedBase and subclasses tests ===============

# ================= START RequestCreation tests ============

def test_request_creation_fields(dummy_node_class):
    m = RequestCreation(
        current_node_id="A",
        current_run_id="B",
        new_request_id="N",
        running_mode="async",
        new_node_type=dummy_node_class,
        args=(1, 2, 3),
        kwargs={'a': 9},
    )
    assert m.current_node_id == "A"
    assert m.current_run_id == "B"
    assert m.new_request_id == "N"
    assert m.running_mode == "async"
    assert m.new_node_type is dummy_node_class
    assert m.args == (1, 2, 3)
    assert m.kwargs == {'a': 9}
    assert dummy_node_class.__name__ in repr(m)
    assert "A" in repr(m)
    assert "N" in repr(m)

# ================ END RequestCreation tests ===============

# ================= START FatalFailure tests ============

def test_fatal_failure_repr(dummy_exception):
    m = FatalFailure(error=dummy_exception)
    assert "Something went wrong" in repr(m)
    assert isinstance(m, RequestCompletionMessage)

# ================ END FatalFailure tests ===============

# ================= START Streaming tests ============

def test_streaming_repr():
    streamed_object = object()
    m = Streaming(streamed_object=streamed_object, node_id="Z1")
    s = repr(m)
    assert "Streaming" in s
    assert "node_id=Z1" in s
    assert str(id(streamed_object)) in s or "streamed_object" in s

def test_streaming_is_a_message():
    m = Streaming(streamed_object="abc", node_id="some_id")
    assert isinstance(m, RequestCompletionMessage)
    assert m.streamed_object == "abc"
    assert m.node_id == "some_id"

# ================ END Streaming tests ===============