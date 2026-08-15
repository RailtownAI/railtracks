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


def test_find_link_returns_the_link_not_the_value():
    chain = ScopeLink(value=1).pushed(2).pushed(3)
    link = chain.find_link(lambda v: v == 2)
    assert isinstance(link, ScopeLink)
    assert link.value == 2
    # the link exposes the position, so .parent is reachable
    assert link.parent.value == 1


def test_find_link_returns_head_when_head_matches():
    chain = ScopeLink(value=1).pushed(2)
    assert chain.find_link(lambda v: v == 2) is chain


def test_find_link_returns_none_when_nothing_matches():
    chain = ScopeLink(value=1).pushed(2)
    assert chain.find_link(lambda v: v == 999) is None


def test_find_link_returns_topmost_match_when_ids_repeat():
    # mirrors NODE_BODY(A) sitting above NODE(A) — same id, different kind.
    chain = (
        ScopeLink(value=("NODE", "A")).pushed(("MW", "m")).pushed(("NODE_BODY", "A"))
    )
    # matching by id alone returns the *topmost* occurrence (positional, not deepest)
    assert chain.find_link(lambda v: v[1] == "A").value == ("NODE_BODY", "A")
    # matching by kind skips the node-body and lands on the NODE entry
    assert chain.find_link(lambda v: v[0] == "NODE").value == ("NODE", "A")


def test_find_link_supports_skip_self_then_walk_below():
    # resolver shape: locate self's own NODE entry, then walk strictly below it.
    chain = (
        ScopeLink(value=("NODE", "caller"))
        .pushed(("NODE", "A"))
        .pushed(("MW", "m"))
        .pushed(("NODE_BODY", "A"))
    )
    self_link = chain.find_link(lambda v: v[0] == "NODE")  # NODE("A") — self's boundary
    assert self_link.value == ("NODE", "A")
    # everything below self is the enclosing world → the caller node
    assert self_link.parent.value == ("NODE", "caller")
