import pytest

from railtracks.built_nodes.gateway_manager import GatewayManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def mapper_a(messages, schema, tools):
    return messages, schema, tools


async def mapper_b(messages, schema, tools):
    return messages, schema, tools


async def mapper_c(messages, schema, tools):
    return messages, schema, tools


def sync_mapper(messages, schema, tools):
    return messages, schema, tools


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def test_empty_construction():
    gm = GatewayManager()
    assert list(gm) == []
    assert len(gm) == 0


def test_construction_with_user_mappers():
    gm = GatewayManager([mapper_a, mapper_b])
    assert list(gm) == [mapper_a, mapper_b]
    assert len(gm) == 2


# ---------------------------------------------------------------------------
# from_user_input
# ---------------------------------------------------------------------------

def test_from_user_input_none():
    gm = GatewayManager.from_user_input(None)
    assert list(gm) == []


def test_from_user_input_list():
    gm = GatewayManager.from_user_input([mapper_a, mapper_b])
    assert list(gm) == [mapper_a, mapper_b]


def test_from_user_input_gateway_manager_copies_user_layer():
    original = GatewayManager([mapper_a])
    copy = GatewayManager.from_user_input(original)
    assert list(copy) == [mapper_a]


def test_from_user_input_gateway_manager_sys_layers_not_copied():
    original = GatewayManager([mapper_a])
    original._add_sys_pre(mapper_b)
    original._add_sys_post(mapper_c)

    copy = GatewayManager.from_user_input(original)

    # sys layers of the original do NOT propagate — each Gateway gets clean sys layers
    assert copy._sys_pre == []
    assert copy._sys_post == []


def test_from_user_input_list_not_mutated():
    user_list = [mapper_a]
    gm = GatewayManager.from_user_input(user_list)
    gm._add_sys_pre(mapper_b)

    # original list is unchanged
    assert user_list == [mapper_a]


def test_from_user_input_gateway_manager_not_mutated():
    original = GatewayManager([mapper_a])
    copy = GatewayManager.from_user_input(original)
    copy._add_sys_pre(mapper_b)

    # original's sys layer is unchanged
    assert original._sys_pre == []


# ---------------------------------------------------------------------------
# System layer management
# ---------------------------------------------------------------------------

def test_add_sys_pre_goes_to_sys_layer():
    gm = GatewayManager([mapper_a])
    gm._add_sys_pre(mapper_b)

    # user layer unchanged
    assert list(gm) == [mapper_a]
    # sys_pre updated
    assert gm._sys_pre == [mapper_b]


def test_add_sys_post_goes_to_sys_layer():
    gm = GatewayManager([mapper_a])
    gm._add_sys_post(mapper_b)

    assert list(gm) == [mapper_a]
    assert gm._sys_post == [mapper_b]


# ---------------------------------------------------------------------------
# Execution order
# ---------------------------------------------------------------------------

def test_execution_order_sys_pre_first():
    gm = GatewayManager([mapper_a])
    gm._add_sys_pre(mapper_b)

    assert gm._execution_order() == [mapper_b, mapper_a]


def test_execution_order_sys_post_last():
    gm = GatewayManager([mapper_a])
    gm._add_sys_post(mapper_b)

    assert gm._execution_order() == [mapper_a, mapper_b]


def test_execution_order_all_three_layers():
    gm = GatewayManager([mapper_a])
    gm._add_sys_pre(mapper_b)
    gm._add_sys_post(mapper_c)

    assert gm._execution_order() == [mapper_b, mapper_a, mapper_c]


def test_execution_order_no_user_mappers():
    gm = GatewayManager()
    gm._add_sys_pre(mapper_a)
    gm._add_sys_post(mapper_b)

    assert gm._execution_order() == [mapper_a, mapper_b]


# ---------------------------------------------------------------------------
# Public interface — exposes user layer only
# ---------------------------------------------------------------------------

def test_getitem():
    gm = GatewayManager([mapper_a, mapper_b])
    gm._add_sys_pre(mapper_c)  # sys layer should not affect indexing

    assert gm[0] is mapper_a
    assert gm[1] is mapper_b


def test_len_counts_user_layer_only():
    gm = GatewayManager([mapper_a, mapper_b])
    gm._add_sys_pre(mapper_c)

    assert len(gm) == 2


def test_iter_yields_user_layer_only():
    gm = GatewayManager([mapper_a, mapper_b])
    gm._add_sys_pre(mapper_c)

    assert list(gm) == [mapper_a, mapper_b]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_non_callable_raises():
    with pytest.raises(TypeError, match="not callable"):
        GatewayManager.from_user_input(["not a function"])  # type: ignore[list-item]


def test_sync_callable_raises():
    with pytest.raises(TypeError, match="async"):
        GatewayManager.from_user_input([sync_mapper])
