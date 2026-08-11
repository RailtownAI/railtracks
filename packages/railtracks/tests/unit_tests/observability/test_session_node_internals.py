import railtracks as rt

# `configure` as a module, not `observer` by name: the test fixture swaps the object
from railtracks.observability import Event, configure, configure_writers
from railtracks.observability.configure import add_inline_listener


def _nodes(payload) -> dict:
    """Serialized nodes of the single run, keyed by name."""
    return {n["name"]: n for n in payload["runs"][0]["nodes"]}


async def test_tool_node_reports_latency():
    @rt.function_node
    def my_tool(x: int) -> int:
        """A tool."""
        return x + 1

    with rt.Session(flow_name="internals-test") as session:
        assert await rt.call(my_tool, 1) == 2

    block = _nodes(session.payload())["my_tool"]["details"]["internals"]
    assert block["latency"]["total_time"] > 0
    # a function node never had the LLM keys at all
    assert "llm_details" not in block


async def test_internals_is_never_null():
    """A null defeats every consumer's `.get("internals", {})` default."""

    @rt.function_node
    def my_tool(x: int) -> int:
        """A tool."""
        return x + 1

    with rt.Session(flow_name="internals-test") as session:
        await rt.call(my_tool, 1)

    for node in session.payload()["runs"][0]["nodes"]:
        assert isinstance(node["details"]["internals"], dict)


async def test_parent_snapshots_carry_a_block_without_latency():
    """Earlier snapshots predate the completion that `latency` measures."""

    @rt.function_node
    def my_tool(x: int) -> int:
        """A tool."""
        return x + 1

    with rt.Session(flow_name="internals-test") as session:
        await rt.call(my_tool, 1)

    for node in session.payload()["runs"][0]["nodes"]:
        parent = node.get("parent")
        while parent is not None:
            assert isinstance(parent["details"]["internals"], dict)
            assert "latency" not in parent["details"]["internals"]
            parent = parent.get("parent")


async def test_nested_nodes_each_get_their_own_block():
    @rt.function_node
    def inner(x: int) -> int:
        """Inner."""
        return x + 1

    @rt.function_node
    async def outer(x: int) -> int:
        """Outer."""
        return await rt.call(inner, x)

    with rt.Session(flow_name="internals-test") as session:
        assert await rt.call(outer, 10) == 11

    nodes = _nodes(session.payload())
    assert set(nodes) == {"outer", "inner"}
    durations = {
        name: node["details"]["internals"]["latency"]["total_time"]
        for name, node in nodes.items()
    }
    assert all(d > 0 for d in durations.values())
    assert durations["outer"] >= durations["inner"]


async def test_a_second_session_does_not_inherit_the_first_ones_nodes():
    """The collector is shared, so its state has to stay keyed by session."""

    @rt.function_node
    def first(x: int) -> int:
        """First."""
        return x

    @rt.function_node
    def second(x: int) -> int:
        """Second."""
        return x

    with rt.Session(flow_name="internals-test") as session_one:
        await rt.call(first, 1)
    with rt.Session(flow_name="internals-test") as session_two:
        await rt.call(second, 2)

    assert set(_nodes(session_one.payload())) == {"first"}
    assert set(_nodes(session_two.payload())) == {"second"}


async def test_collecting_does_not_disturb_caller_writers():
    """The collector runs inline, so it neither replaces nor joins the writer set."""

    class _Noop:
        async def start(self): ...
        async def write(self, event: Event): ...
        async def shutdown(self): ...

    mine = _Noop()
    configure_writers([mine])

    with rt.Session(flow_name="internals-test"):
        pass

    assert configure.observer._pending_writers == [mine]


def test_collecting_creates_no_consumer_task():
    """A Writer would bring a queue and a consumer task, and that task binds to the
    loop that created it — which breaks under a nested MCP loop or across threads."""
    import asyncio

    async def run_session():
        with rt.Session(flow_name="internals-test"):
            pass
        return [t.get_name() for t in asyncio.all_tasks()]

    task_names = asyncio.run(run_session())
    assert not [n for n in task_names if n.startswith("observer-consumer:")]


async def test_add_inline_listener_is_idempotent():
    """Every Session registers the shared collector; it must land only once."""
    calls = []
    listener = calls.append

    assert add_inline_listener(listener) is True
    assert add_inline_listener(listener) is False
    assert configure.inline_listeners().count(listener) == 1
