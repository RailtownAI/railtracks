from railtracks.context.scope_link import ScopeLink


def test_single_link_current_value_and_no_parent():
    link = ScopeLink(value="a")
    assert link.value == "a"
    assert link.parent is None


def test_pushed_creates_new_link_with_previous_as_parent():
    root = ScopeLink(value="a")
    child = root.pushed("b")
    assert child.value == "b"
    assert child.parent is root
    # pushing never mutates the original
    assert root.value == "a"
    assert root.parent is None


def test_find_walks_up_to_matching_ancestor():
    chain = ScopeLink(value=1).pushed(2).pushed(3)
    assert chain.find(lambda v: v == 1) == 1
    assert chain.find(lambda v: v == 3) == 3


def test_find_returns_none_when_nothing_matches():
    chain = ScopeLink(value=1).pushed(2)
    assert chain.find(lambda v: v == 999) is None


def test_generic_reuse_with_different_value_types():
    int_chain = ScopeLink(value=1).pushed(2)
    str_chain = ScopeLink(value="x").pushed("y")
    assert int_chain.find(lambda v: v == 2) == 2
    assert str_chain.find(lambda v: v == "y") == "y"
