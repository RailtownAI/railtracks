from railtracks.utils.logging.action import RequestSuccessAction, RequestCreationAction, RequestFailureAction


def test_request_success_action():
    node_name = "example"
    output = "success"
    action = RequestSuccessAction(
        node_name,
        output
    )

    assert action.to_logging_msg() == "example DONE"

def test_request_failure_action():
    node_name = "example"
    exc = Exception("An error occurred")
    action = RequestFailureAction(
        node_name,
        exc
    )

    assert action.to_logging_msg() == "example FAILED"

def test_request_creation_action():
    child_node_name = "child"
    parent_node_name = "parent"


    action = RequestCreationAction(
        parent_node_name,
        child_node_name,
        input_args=(),
        input_kwargs={}
    )

    assert action.to_logging_msg() == "parent CREATED child"


