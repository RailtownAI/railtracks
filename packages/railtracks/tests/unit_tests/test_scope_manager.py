from railtracks.scope_manager import NullScopeManager, null_scope_manager


def test_null_scope_manager_enter_node_is_a_noop():
    manager = NullScopeManager()
    with manager.enter_node("node-1"):
        pass


def test_null_scope_manager_enter_node_body_is_a_noop():
    manager = NullScopeManager()
    with manager.enter_node_body():
        pass


def test_null_scope_manager_enter_middleware_yields_none():
    manager = NullScopeManager()
    with manager.enter_middleware("some-middleware") as middleware_id:
        assert middleware_id is None


def test_null_scope_manager_getter_returns_shared_singleton():
    a = null_scope_manager()
    b = null_scope_manager()
    assert a is b
    assert isinstance(a, NullScopeManager)
