import asyncio
import pytest
from railtracks.nodes.nodes import DebugDetails, Node

from railtracks.context.central import get_session_id, get_run_id, get_parent_id, get_middleware_id, get_current_scope
from railtracks.context.session_context import ScopeKind
from railtracks.middleware.core import wrap_node
import railtracks as rt


class BottomLevel(Node):
    def __init__(self, ):
        super().__init__()
        

    async def invoke(self,  expected_session_id: str | None, expected_run_id: str | None):
        session_id = get_session_id()
        run_id = get_run_id()
        parent_id = get_parent_id()

        assert session_id == expected_session_id
        assert run_id == expected_run_id
        assert parent_id == self.uuid

        return {
            "session_id": session_id,
            "run_id": run_id,
            "parent_id": parent_id
        }
    
    @classmethod
    def name(cls):
        return "Top Level"
    
    @classmethod
    def type(cls):
        return "Tool"


class TopLevel(Node):
    def __init__(self, ):
        super().__init__()


    async def invoke(self, number_trials: int, expected_session_id: str | None):
        session_id = get_session_id()
        run_id = get_run_id()
        parent_id = get_parent_id()

        assert session_id == expected_session_id
        assert run_id == self.uuid
        assert parent_id == self.uuid
        contracts = [rt.call(BottomLevel, expected_session_id, self.uuid) for _ in range(number_trials)]
        return await asyncio.gather(*contracts)
    
    @classmethod
    def name(cls):
        return "Top Level"
    
    @classmethod
    def type(cls):
        return "Tool"


@pytest.mark.asyncio
@pytest.mark.parametrize("num_trials", [1, 5, 10, 50])
async def test_run_id_propagation(num_trials):
    
    with rt.Session(name="test_session") as session:
        await rt.call(TopLevel, num_trials, session._identifier)


@pytest.mark.asyncio
@pytest.mark.parametrize("num_trials", [1, 5,])
async def test_run_id_propagation_multiple_runs(num_trials):
    
    with rt.Session(name="test_session") as session:
        await rt.call(TopLevel, num_trials, session._identifier)
        await rt.call(TopLevel, num_trials, session._identifier)
        await rt.call(TopLevel, num_trials, session._identifier)
        await rt.call(TopLevel, num_trials, session._identifier)


@pytest.mark.asyncio
@pytest.mark.parametrize("num_trials", [1, 5,])
async def test_run_id_propagation_multiple_runs_parallel(num_trials):
    
    with rt.Session(name="test_session") as session:
        contracts = [rt.call(TopLevel, num_trials, session._identifier) for _ in range(4)]
        await asyncio.gather(*contracts)



@pytest.mark.asyncio
@pytest.mark.parametrize("num_trials", [1, 5,])
async def test_run_id_propagation_multiple_sessions(num_trials):
    
    with rt.Session(name="test_session") as session:
        await rt.call(TopLevel, num_trials, session._identifier)
        await rt.call(TopLevel, num_trials, session._identifier)
        await rt.call(TopLevel, num_trials, session._identifier)
        await rt.call(TopLevel, num_trials, session._identifier)

    with rt.Session(name="test_session_2") as session:
        await rt.call(TopLevel, num_trials, session._identifier)
        await rt.call(TopLevel, num_trials, session._identifier)
        await rt.call(TopLevel, num_trials, session._identifier)

@pytest.mark.asyncio
@pytest.mark.parametrize("num_trials", [1, 5,])
async def test_run_id_propagation_multiple_sessions_parallel(num_trials):

    async def runner():
    
        with rt.Session(name="test_session") as session:
            await rt.call(TopLevel, num_trials, session._identifier)
            await rt.call(TopLevel, num_trials, session._identifier)
        

    await asyncio.gather(runner(), runner())


CAPTURED = {}


class ChildNode(Node):
    async def invoke(self):
        scope = get_current_scope()
        # skip this node's own NODE_BODY/NODE entries to find its actual parent
        link = scope
        while link is not None and link.value.id == self.uuid:
            link = link.parent
        CAPTURED["child_immediate_ancestor_kind"] = link.value.kind if link else None
        CAPTURED["child_immediate_ancestor_id"] = link.value.id if link else None
        return "child-done"

    @classmethod
    def name(cls):
        return "Child Node"

    @classmethod
    def type(cls):
        return "Tool"


class ParentNode(Node):
    async def invoke(self):
        return "parent-done"

    @classmethod
    def name(cls):
        return "Parent Node"

    @classmethod
    def type(cls):
        return "Tool"


@wrap_node
async def capturing_middleware(call, *args, **kwargs):
    CAPTURED["middleware_parent_id"] = get_parent_id()
    CAPTURED["middleware_id_at_entry"] = get_middleware_id()
    await rt.call(ChildNode)
    return await call(*args, **kwargs)


ParentWithMiddleware = ParentNode.extend_middleware(capturing_middleware)


@pytest.mark.asyncio
async def test_middleware_fired_call_lands_under_the_middleware_not_the_node_body():
    CAPTURED.clear()
    with rt.Session(name="test_session"):
        await rt.call(ParentWithMiddleware)

    assert CAPTURED["middleware_parent_id"] is not None
    assert CAPTURED["middleware_id_at_entry"] is not None
    assert CAPTURED["child_immediate_ancestor_kind"] == ScopeKind.MIDDLEWARE
    assert CAPTURED["child_immediate_ancestor_id"] == CAPTURED["middleware_id_at_entry"]